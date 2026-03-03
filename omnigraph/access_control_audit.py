"""
OmniGraph: Enterprise AI Knowledge Graph Database System
========================================================
Module: Access Control & Audit

Enforces role-based access control (RBAC), validates user permissions,
logs all queries and access events, tracks sensitive document access,
and provides audit trail reporting.

Author: OmniGraph Team
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psycopg2

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omnigraph.access_control")


class AccessControlManager:
    """
    Manages role-based access control, permission validation,
    and comprehensive audit logging.

    Responsibilities:
    - Validate user permissions before resource access
    - Enforce sensitivity-level-based access policies
    - Log all queries for audit trail
    - Track sensitive document access
    - Provide audit reporting for compliance
    """

    def __init__(self, db_connection):
        """
        Parameters
        ----------
        db_connection : DatabaseConnection
            Active database connection.
        """
        self.db = db_connection

    # ------------------------------------------------------------------
    # Access Control
    # ------------------------------------------------------------------

    def check_access(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int,
        action: str = "read",
    ) -> bool:
        """
        Check whether a user has permission to perform an action on a resource.

        Parameters
        ----------
        user_id : int
            The user requesting access.
        resource_type : str
            Type of resource ('document', 'entity', 'concept', 'audit_log').
        resource_id : int
            ID of the specific resource.
        action : str
            Action type: 'read', 'write', or 'delete'.

        Returns
        -------
        bool
            True if access is granted, False if denied.
        """
        # Determine sensitivity level
        sensitivity = self._get_resource_sensitivity(resource_type, resource_id)
        if sensitivity is None:
            logger.warning(
                "Resource not found: %s #%d", resource_type, resource_id,
            )
            return False

        # Check against user's role-based policies
        has_access = self._evaluate_policies(
            user_id, resource_type, sensitivity, action,
        )

        # Log the access attempt
        if has_access:
            if sensitivity in ("confidential", "restricted"):
                self.log_audit(
                    user_id=user_id,
                    action="view",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=f"Accessed {sensitivity} {resource_type} #{resource_id}",
                )
            logger.info(
                "Access GRANTED: user=%d, %s #%d (%s), action=%s",
                user_id, resource_type, resource_id, sensitivity, action,
            )
        else:
            self.log_audit(
                user_id=user_id,
                action="access_denied",
                resource_type=resource_type,
                resource_id=resource_id,
                details=f"Denied {action} access to {sensitivity} {resource_type} #{resource_id}",
            )
            logger.warning(
                "Access DENIED: user=%d, %s #%d (%s), action=%s",
                user_id, resource_type, resource_id, sensitivity, action,
            )

        return has_access

    def validate_permission(
        self,
        user_id: int,
        required_permission: str,
    ) -> bool:
        """
        Check if a user has a specific permission via any of their roles.

        Parameters
        ----------
        user_id : int
            User to check.
        required_permission : str
            Permission string (e.g., 'manage_users', 'view_audit').

        Returns
        -------
        bool
            True if the user has the permission.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT r.permissions
                FROM omnigraph.user_roles ur
                JOIN omnigraph.roles r ON r.role_id = ur.role_id
                WHERE ur.user_id = %s
                """,
                (user_id,),
            )
            for row in cur.fetchall():
                permissions = row[0] if row[0] else []
                if required_permission in permissions:
                    return True
            return False

        except psycopg2.Error as exc:
            logger.error("Permission validation failed: %s", exc)
            return False

    def get_user_roles(self, user_id: int) -> List[Dict]:
        """Retrieve all roles assigned to a user."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT r.role_id, r.role_name, r.description, r.permissions,
                       ur.assigned_at
                FROM omnigraph.user_roles ur
                JOIN omnigraph.roles r ON r.role_id = ur.role_id
                WHERE ur.user_id = %s
                ORDER BY r.role_name
                """,
                (user_id,),
            )
            columns = ["role_id", "role_name", "description",
                        "permissions", "assigned_at"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Failed to get user roles: %s", exc)
            return []

    def get_user_access_matrix(self, user_id: int) -> List[Dict]:
        """
        Get the complete access matrix for a user across all resource types
        and sensitivity levels.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                    ap.resource_type,
                    ap.sensitivity_level,
                    BOOL_OR(ap.can_read) AS can_read,
                    BOOL_OR(ap.can_write) AS can_write,
                    BOOL_OR(ap.can_delete) AS can_delete
                FROM omnigraph.user_roles ur
                JOIN omnigraph.access_policies ap ON ap.role_id = ur.role_id
                WHERE ur.user_id = %s
                GROUP BY ap.resource_type, ap.sensitivity_level
                ORDER BY ap.resource_type, ap.sensitivity_level
                """,
                (user_id,),
            )
            columns = ["resource_type", "sensitivity_level",
                        "can_read", "can_write", "can_delete"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Failed to get access matrix: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Audit Logging
    # ------------------------------------------------------------------

    def log_query(
        self,
        user_id: int,
        query_text: str,
        query_type: str,
        results_count: int = 0,
        execution_ms: int = 0,
    ) -> Optional[int]:
        """
        Log a query execution for audit purposes.

        Parameters
        ----------
        user_id : int
            User who executed the query.
        query_text : str
            The query text.
        query_type : str
            Type: keyword_search, semantic_search, graph_traversal, etc.
        results_count : int
            Number of results returned.
        execution_ms : int
            Query execution time in milliseconds.

        Returns
        -------
        int or None
            The log_id.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.query_logs
                    (user_id, query_text, query_type, results_count, execution_ms)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING log_id
                """,
                (user_id, query_text, query_type, results_count, execution_ms),
            )
            log_id = cur.fetchone()[0]
            self.db.conn.commit()
            return log_id

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to log query: %s", exc)
            return None

    def log_audit(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create an audit log entry.

        Parameters
        ----------
        user_id : int
            User performing the action.
        action : str
            Action: view, create, update, delete, export, access_denied, etc.
        resource_type : str
            Resource being acted upon.
        resource_id : int, optional
            Specific resource ID.
        details : str, optional
            Additional details.
        ip_address : str, optional
            Client IP address.

        Returns
        -------
        int or None
            The audit_id.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.audit_logs
                    (user_id, action, resource_type, resource_id,
                     details, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING audit_id
                """,
                (user_id, action, resource_type, resource_id,
                 details, ip_address),
            )
            audit_id = cur.fetchone()[0]
            self.db.conn.commit()
            return audit_id

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to create audit log: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Audit Reporting
    # ------------------------------------------------------------------

    def get_audit_trail(
        self,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Retrieve filtered audit trail.

        Parameters
        ----------
        user_id : int, optional
            Filter by user.
        resource_type : str, optional
            Filter by resource type.
        action : str, optional
            Filter by action type.
        days : int
            Look back N days.
        limit : int
            Max results.

        Returns
        -------
        list of dict
            Audit log entries.
        """
        cur = self.db.conn.cursor()
        try:
            conditions = ["al.created_at >= %s"]
            params: list = [datetime.now() - timedelta(days=days)]

            if user_id:
                conditions.append("al.user_id = %s")
                params.append(user_id)
            if resource_type:
                conditions.append("al.resource_type = %s")
                params.append(resource_type)
            if action:
                conditions.append("al.action = %s")
                params.append(action)

            params.append(limit)
            where_clause = " AND ".join(conditions)

            cur.execute(
                f"""
                SELECT
                    al.audit_id,
                    al.created_at,
                    u.full_name,
                    u.department,
                    al.action,
                    al.resource_type,
                    al.resource_id,
                    al.details,
                    al.ip_address
                FROM omnigraph.audit_logs al
                JOIN omnigraph.users u ON u.user_id = al.user_id
                WHERE {where_clause}
                ORDER BY al.created_at DESC
                LIMIT %s
                """,
                params,
            )

            columns = ["audit_id", "timestamp", "user", "department",
                        "action", "resource_type", "resource_id",
                        "details", "ip_address"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Audit trail retrieval failed: %s", exc)
            return []

    def get_sensitive_access_report(self, days: int = 30) -> List[Dict]:
        """
        Generate a report of all access to confidential/restricted documents.
        Used by compliance officers for monitoring.
        """
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                    al.created_at,
                    u.full_name,
                    u.department,
                    STRING_AGG(DISTINCT r.role_name, ', ') AS roles,
                    al.action,
                    d.title AS document_title,
                    d.sensitivity_level,
                    al.details,
                    al.ip_address
                FROM omnigraph.audit_logs al
                JOIN omnigraph.users u ON u.user_id = al.user_id
                LEFT JOIN omnigraph.documents d ON d.document_id = al.resource_id
                LEFT JOIN omnigraph.user_roles ur ON ur.user_id = al.user_id
                LEFT JOIN omnigraph.roles r ON r.role_id = ur.role_id
                WHERE al.resource_type = 'document'
                  AND d.sensitivity_level IN ('confidential', 'restricted')
                  AND al.created_at >= %s
                GROUP BY al.audit_id, al.created_at, u.full_name,
                         u.department, al.action, d.title,
                         d.sensitivity_level, al.details, al.ip_address
                ORDER BY al.created_at DESC
                """,
                (datetime.now() - timedelta(days=days),),
            )

            columns = ["timestamp", "user", "department", "roles",
                        "action", "document", "sensitivity", "details",
                        "ip_address"]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

        except psycopg2.Error as exc:
            logger.error("Sensitive access report failed: %s", exc)
            return []

    def get_query_analytics(self, days: int = 30) -> Dict:
        """
        Generate query analytics summary for the specified period.
        """
        cur = self.db.conn.cursor()
        try:
            since = datetime.now() - timedelta(days=days)

            cur.execute(
                """
                SELECT COUNT(*), query_type,
                       ROUND(AVG(execution_ms)::NUMERIC, 1),
                       ROUND(AVG(results_count)::NUMERIC, 1)
                FROM omnigraph.query_logs
                WHERE created_at >= %s
                GROUP BY query_type
                ORDER BY COUNT(*) DESC
                """,
                (since,),
            )
            by_type = []
            for row in cur.fetchall():
                by_type.append({
                    "count": row[0],
                    "query_type": row[1],
                    "avg_execution_ms": float(row[2]) if row[2] else 0,
                    "avg_results": float(row[3]) if row[3] else 0,
                })

            cur.execute(
                """
                SELECT u.full_name, COUNT(*) AS query_count
                FROM omnigraph.query_logs ql
                JOIN omnigraph.users u ON u.user_id = ql.user_id
                WHERE ql.created_at >= %s
                GROUP BY u.user_id, u.full_name
                ORDER BY query_count DESC
                LIMIT 10
                """,
                (since,),
            )
            top_users = [{"user": r[0], "query_count": r[1]} for r in cur.fetchall()]

            return {
                "period_days": days,
                "by_type": by_type,
                "top_users": top_users,
            }

        except psycopg2.Error as exc:
            logger.error("Query analytics failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # User Management Support
    # ------------------------------------------------------------------

    def assign_role(
        self,
        user_id: int,
        role_id: int,
        assigned_by: int,
    ) -> bool:
        """Assign a role to a user."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO omnigraph.user_roles (user_id, role_id, assigned_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, role_id) DO NOTHING
                """,
                (user_id, role_id, assigned_by),
            )
            self.db.conn.commit()

            self.log_audit(
                user_id=assigned_by,
                action="update",
                resource_type="role",
                resource_id=user_id,
                details=f"Assigned role {role_id} to user {user_id}",
            )
            return True

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to assign role: %s", exc)
            return False

    def revoke_role(self, user_id: int, role_id: int, revoked_by: int) -> bool:
        """Revoke a role from a user."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                DELETE FROM omnigraph.user_roles
                WHERE user_id = %s AND role_id = %s
                """,
                (user_id, role_id),
            )
            self.db.conn.commit()

            self.log_audit(
                user_id=revoked_by,
                action="delete",
                resource_type="role",
                resource_id=user_id,
                details=f"Revoked role {role_id} from user {user_id}",
            )
            return True

        except psycopg2.Error as exc:
            self.db.conn.rollback()
            logger.error("Failed to revoke role: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _get_resource_sensitivity(
        self,
        resource_type: str,
        resource_id: int,
    ) -> Optional[str]:
        """Get the sensitivity level of a resource."""
        cur = self.db.conn.cursor()
        try:
            if resource_type == "document":
                cur.execute(
                    "SELECT sensitivity_level FROM omnigraph.documents WHERE document_id = %s",
                    (resource_id,),
                )
            else:
                return "public"  # Non-document resources default to public

            row = cur.fetchone()
            return row[0] if row else None

        except psycopg2.Error as exc:
            logger.error("Failed to get resource sensitivity: %s", exc)
            return None

    def _evaluate_policies(
        self,
        user_id: int,
        resource_type: str,
        sensitivity: str,
        action: str,
    ) -> bool:
        """Evaluate access policies for user's roles."""
        cur = self.db.conn.cursor()
        try:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM omnigraph.user_roles ur
                    JOIN omnigraph.access_policies ap ON ur.role_id = ap.role_id
                    WHERE ur.user_id = %s
                      AND ap.resource_type = %s
                      AND ap.sensitivity_level = %s
                      AND (
                          (%s = 'read'   AND ap.can_read = TRUE) OR
                          (%s = 'write'  AND ap.can_write = TRUE) OR
                          (%s = 'delete' AND ap.can_delete = TRUE)
                      )
                )
                """,
                (user_id, resource_type, sensitivity,
                 action, action, action),
            )
            return cur.fetchone()[0]

        except psycopg2.Error as exc:
            logger.error("Policy evaluation failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Module Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from ingestion_pipeline import DatabaseConnection

    db = DatabaseConnection()
    db.connect()

    acm = AccessControlManager(db)

    # Check access for different users
    print("=== Access Control Checks ===")
    checks = [
        (1, "document", 1, "read",   "Admin → public doc"),
        (8, "document", 5, "read",   "Consumer → restricted doc"),
        (5, "document", 5, "read",   "Compliance → restricted doc"),
        (10, "document", 2, "write", "Consumer → confidential doc write"),
    ]
    for uid, rtype, rid, action, desc in checks:
        result = acm.check_access(uid, rtype, rid, action)
        status = "✓ GRANTED" if result else "✗ DENIED"
        print(f"  {status}  {desc}")

    # User roles
    print("\n=== User Roles (Priya, id=1) ===")
    roles = acm.get_user_roles(1)
    for r in roles:
        print(f"  {r['role_name']}: {r['permissions']}")

    # Access matrix
    print("\n=== Access Matrix (Consumer, id=8) ===")
    matrix = acm.get_user_access_matrix(8)
    for m in matrix:
        print(f"  {m['resource_type']}/{m['sensitivity_level']}: "
              f"R={m['can_read']} W={m['can_write']} D={m['can_delete']}")

    # Audit trail
    print("\n=== Recent Audit Trail ===")
    trail = acm.get_audit_trail(days=365, limit=5)
    for entry in trail:
        print(f"  [{entry['timestamp']}] {entry['user']}: "
              f"{entry['action']} on {entry['resource_type']}")

    db.disconnect()
