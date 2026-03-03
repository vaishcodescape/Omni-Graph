-- ============================================================================
-- OmniGraph: Enterprise AI Knowledge Graph Database System
-- Sample Data Population Script
-- ============================================================================
-- Run AFTER schema.sql
-- Usage: psql -d omnigraph -f sql/sample_data.sql
-- ============================================================================

SET search_path TO omnigraph;

-- ============================================================================
-- ROLES
-- ============================================================================
INSERT INTO roles (role_name, description, permissions) VALUES
    ('admin',       'System administrator with full access',                    ARRAY['read', 'write', 'delete', 'manage_users', 'manage_policies', 'view_audit']),
    ('contributor',  'Knowledge contributor who uploads and enriches documents', ARRAY['read', 'write', 'tag', 'upload']),
    ('consumer',     'Knowledge consumer who searches and retrieves',           ARRAY['read', 'search']),
    ('expert',       'Domain expert who manages taxonomy and concepts',         ARRAY['read', 'write', 'manage_taxonomy', 'approve']),
    ('compliance',   'Compliance officer who audits access and usage',          ARRAY['read', 'view_audit', 'export_audit']);

-- ============================================================================
-- USERS
-- ============================================================================
INSERT INTO users (username, email, full_name, department, title, password_hash) VALUES
    ('agarwal.priya',   'priya.agarwal@omnigraph.io',   'Priya Agarwal',        'Engineering',      'VP of Engineering',            'pbkdf2:sha256:260000$salt$hash_priya'),
    ('chen.wei',        'wei.chen@omnigraph.io',        'Wei Chen',             'Data Science',     'Lead Data Scientist',          'pbkdf2:sha256:260000$salt$hash_wei'),
    ('johnson.mark',    'mark.johnson@omnigraph.io',    'Mark Johnson',         'Security',         'Chief Security Officer',       'pbkdf2:sha256:260000$salt$hash_mark'),
    ('martinez.sofia',  'sofia.martinez@omnigraph.io',  'Sofia Martinez',       'Research',         'Senior Research Scientist',    'pbkdf2:sha256:260000$salt$hash_sofia'),
    ('okafor.emeka',    'emeka.okafor@omnigraph.io',    'Emeka Okafor',         'Compliance',       'Compliance Director',          'pbkdf2:sha256:260000$salt$hash_emeka'),
    ('tanaka.yuki',     'yuki.tanaka@omnigraph.io',     'Yuki Tanaka',          'Engineering',      'Senior Software Engineer',     'pbkdf2:sha256:260000$salt$hash_yuki'),
    ('williams.alex',   'alex.williams@omnigraph.io',   'Alex Williams',        'IT Operations',    'DevOps Lead',                  'pbkdf2:sha256:260000$salt$hash_alex'),
    ('kumar.rahul',     'rahul.kumar@omnigraph.io',     'Rahul Kumar',          'Product',          'Product Manager',              'pbkdf2:sha256:260000$salt$hash_rahul'),
    ('fischer.anna',    'anna.fischer@omnigraph.io',     'Anna Fischer',         'Data Science',     'ML Engineer',                  'pbkdf2:sha256:260000$salt$hash_anna'),
    ('brown.david',     'david.brown@omnigraph.io',     'David Brown',          'Engineering',      'Junior Developer',             'pbkdf2:sha256:260000$salt$hash_david');

-- ============================================================================
-- USER_ROLES
-- ============================================================================
INSERT INTO user_roles (user_id, role_id, assigned_by) VALUES
    (1, 1, NULL),   -- Priya: admin
    (1, 4, NULL),   -- Priya: expert
    (2, 4, 1),      -- Wei: expert
    (2, 2, 1),      -- Wei: contributor
    (3, 1, 1),      -- Mark: admin
    (3, 5, 1),      -- Mark: compliance
    (4, 4, 1),      -- Sofia: expert
    (4, 2, 1),      -- Sofia: contributor
    (5, 5, 1),      -- Emeka: compliance
    (6, 2, 1),      -- Yuki: contributor
    (7, 2, 1),      -- Alex: contributor
    (8, 3, 1),      -- Rahul: consumer
    (9, 2, 1),      -- Anna: contributor
    (9, 4, 1),      -- Anna: expert
    (10, 3, 1);     -- David: consumer

-- ============================================================================
-- ACCESS_POLICIES
-- ============================================================================
INSERT INTO access_policies (role_id, resource_type, sensitivity_level, can_read, can_write, can_delete) VALUES
    -- Admin: full access to everything
    (1, 'document',   'public',        TRUE,  TRUE,  TRUE),
    (1, 'document',   'internal',      TRUE,  TRUE,  TRUE),
    (1, 'document',   'confidential',  TRUE,  TRUE,  TRUE),
    (1, 'document',   'restricted',    TRUE,  TRUE,  TRUE),
    (1, 'entity',     'public',        TRUE,  TRUE,  TRUE),
    (1, 'audit_log',  'public',        TRUE,  FALSE, FALSE),
    -- Contributor: read/write public and internal, read confidential
    (2, 'document',   'public',        TRUE,  TRUE,  FALSE),
    (2, 'document',   'internal',      TRUE,  TRUE,  FALSE),
    (2, 'document',   'confidential',  TRUE,  FALSE, FALSE),
    (2, 'entity',     'public',        TRUE,  TRUE,  FALSE),
    -- Consumer: read-only public and internal
    (3, 'document',   'public',        TRUE,  FALSE, FALSE),
    (3, 'document',   'internal',      TRUE,  FALSE, FALSE),
    (3, 'entity',     'public',        TRUE,  FALSE, FALSE),
    -- Expert: read/write all document levels, manage concepts
    (4, 'document',   'public',        TRUE,  TRUE,  FALSE),
    (4, 'document',   'internal',      TRUE,  TRUE,  FALSE),
    (4, 'document',   'confidential',  TRUE,  TRUE,  FALSE),
    (4, 'concept',    'public',        TRUE,  TRUE,  TRUE),
    -- Compliance: read everything including audit logs
    (5, 'document',   'public',        TRUE,  FALSE, FALSE),
    (5, 'document',   'internal',      TRUE,  FALSE, FALSE),
    (5, 'document',   'confidential',  TRUE,  FALSE, FALSE),
    (5, 'document',   'restricted',    TRUE,  FALSE, FALSE),
    (5, 'audit_log',  'public',        TRUE,  FALSE, FALSE);

-- ============================================================================
-- TAXONOMY
-- ============================================================================
INSERT INTO taxonomy (name, description, parent_id, level, domain) VALUES
    ('Technology',              'All technology-related knowledge',     NULL, 0, 'technology'),
    ('Artificial Intelligence', 'AI and machine learning',             1,    1, 'technology'),
    ('Cybersecurity',           'Security and threat intelligence',    1,    1, 'technology'),
    ('Cloud Computing',         'Cloud infrastructure and services',   1,    1, 'technology'),
    ('Deep Learning',           'Neural networks and deep learning',   2,    2, 'technology'),
    ('Natural Language Processing', 'NLP and text analytics',          2,    2, 'technology'),
    ('Computer Vision',         'Image and video analysis',            2,    2, 'technology'),
    ('Network Security',        'Network protection and monitoring',   3,    2, 'technology'),
    ('Application Security',    'Secure software development',         3,    2, 'technology'),
    ('AWS',                     'Amazon Web Services',                 4,    2, 'technology'),
    ('Azure',                   'Microsoft Azure cloud',               4,    2, 'technology'),
    ('Business',                'Business and management',             NULL, 0, 'business'),
    ('Project Management',      'Project planning and execution',      12,   1, 'business'),
    ('Data Analytics',          'Business intelligence and analytics', 12,   1, 'business'),
    ('Research',                'Academic and industrial research',     NULL, 0, 'research');

-- ============================================================================
-- DOCUMENTS
-- ============================================================================
INSERT INTO documents (title, source_type, content, summary, content_hash, file_path, file_size_bytes, mime_type, sensitivity_level, taxonomy_id, uploaded_by) VALUES
    ('Transformer Architecture in Enterprise NLP',
     'research_paper',
     'This paper explores the application of transformer-based architectures in enterprise natural language processing systems. We present a novel approach to fine-tuning large language models for domain-specific knowledge extraction. Our methodology leverages transfer learning with attention mechanisms optimized for organizational document understanding. Results demonstrate 23% improvement in entity recognition accuracy compared to traditional approaches. The system processes documents across multiple departments including engineering, legal, and finance, creating unified semantic representations.',
     'Novel transformer architecture for enterprise NLP with 23% accuracy improvement',
     'a1b2c3d4e5f6789012345678abcdef01', '/docs/research/transformer_enterprise.pdf', 2458000, 'application/pdf',
     'internal', 6, 4),

    ('Zero Trust Security Framework Implementation Guide',
     'technical_doc',
     'This guide provides a comprehensive framework for implementing Zero Trust Architecture in enterprise environments. Zero Trust eliminates implicit trust and continuously validates every stage of digital interaction. Key components include: microsegmentation, least privilege access, multi-factor authentication, continuous monitoring, and automated threat response. The guide covers network architecture redesign, identity and access management integration, data classification requirements, and compliance mapping for SOC2, ISO 27001, and NIST frameworks.',
     'Comprehensive guide for Zero Trust Architecture implementation',
     'b2c3d4e5f6789012345678abcdef0102', '/docs/security/zero_trust_guide.pdf', 3200000, 'application/pdf',
     'confidential', 8, 3),

    ('Cloud Migration Strategy Q4 2025',
     'report',
     'This report outlines the organizational strategy for migrating legacy on-premises infrastructure to a hybrid cloud architecture. Phase 1 focuses on non-critical workloads migration to AWS and Azure. Phase 2 addresses database migration with zero-downtime requirements. Phase 3 covers containerization of microservices using Kubernetes. Cost analysis projects 35% reduction in infrastructure spend over 3 years. Risk assessment identifies data sovereignty, vendor lock-in, and skill gaps as primary concerns.',
     'Hybrid cloud migration strategy with 35% cost reduction projection',
     'c3d4e5f6789012345678abcdef010203', '/docs/strategy/cloud_migration_q4.pdf', 1800000, 'application/pdf',
     'confidential', 4, 7),

    ('Machine Learning Pipeline Best Practices',
     'technical_doc',
     'A comprehensive guide to building production-ready machine learning pipelines. Covers data preprocessing, feature engineering, model selection, hyperparameter tuning, model validation, deployment strategies, and monitoring. Emphasizes MLOps principles including version control for data and models, automated testing, CI/CD integration, and model drift detection. Includes case studies from recommendation systems, fraud detection, and predictive maintenance implementations.',
     'Guide to production ML pipelines with MLOps best practices',
     'd4e5f6789012345678abcdef01020304', '/docs/engineering/ml_pipeline.md', 980000, 'text/markdown',
     'internal', 2, 2),

    ('Q3 Security Incident Response Report',
     'report',
     'Quarterly report documenting security incidents and response actions. In Q3, the security team handled 47 incidents: 12 phishing attempts, 8 malware detections, 15 unauthorized access attempts, 7 data exfiltration alerts, and 5 DDoS mitigation events. Mean time to detect decreased from 4.2 hours to 2.8 hours. Mean time to respond improved from 6.1 hours to 3.5 hours. Recommendations include additional endpoint protection, enhanced email filtering, and mandatory security awareness training.',
     'Q3 security incident summary: 47 incidents, improved detection/response times',
     'e5f6789012345678abcdef0102030405', '/docs/security/q3_incident_report.pdf', 1500000, 'application/pdf',
     'restricted', 3, 3),

    ('Kubernetes Orchestration Patterns',
     'technical_doc',
     'Reference documentation for container orchestration patterns using Kubernetes. Covers deployment strategies (rolling updates, blue-green, canary), service mesh integration with Istio, horizontal pod autoscaling, persistent volume management, secrets rotation, and network policies. Includes Helm chart templates for common microservice architectures and GitOps workflow integration with ArgoCD.',
     'Kubernetes orchestration patterns and deployment strategies',
     'f6789012345678abcdef010203040506', '/docs/engineering/k8s_patterns.md', 750000, 'text/markdown',
     'internal', 4, 6),

    ('Data Governance Policy Framework',
     'report',
     'Enterprise data governance policy establishing data classification standards, retention policies, access control requirements, and compliance obligations. Defines four data sensitivity levels: public, internal, confidential, and restricted. Establishes data stewardship roles, metadata management standards, and data quality metrics. Addresses GDPR, CCPA, and HIPAA compliance requirements with specific technical controls for each regulation.',
     'Enterprise data governance policy with classification and compliance standards',
     '789012345678abcdef01020304050607', '/docs/compliance/data_governance.pdf', 2100000, 'application/pdf',
     'internal', 12, 5),

    ('Neural Network Optimization Techniques',
     'research_paper',
     'Research paper investigating advanced optimization techniques for deep neural networks including adaptive learning rate methods (Adam, AdaGrad, RMSprop), gradient clipping, batch normalization, dropout regularization, and mixed-precision training. Experimental results on ImageNet and GLUE benchmarks demonstrate that combining cyclical learning rates with gradient accumulation achieves state-of-the-art performance while reducing training time by 40%. Analysis includes convergence proofs and computational complexity bounds.',
     'Deep learning optimization achieving 40% training time reduction',
     '9012345678abcdef0102030405060708', '/docs/research/nn_optimization.pdf', 3100000, 'application/pdf',
     'public', 5, 4),

    ('API Gateway Design and Implementation',
     'technical_doc',
     'Technical documentation for the enterprise API gateway supporting REST and GraphQL endpoints. Covers rate limiting, authentication (OAuth 2.0, JWT, API keys), request/response transformation, caching strategies, circuit breaker patterns, and observability integration. Includes performance benchmarks showing the gateway handles 50,000 requests per second with p99 latency under 15ms.',
     'API gateway design supporting 50K RPS with sub-15ms p99 latency',
     '012345678abcdef010203040506070809', '/docs/engineering/api_gateway.md', 620000, 'text/markdown',
     'internal', 1, 1),

    ('Predictive Analytics for Supply Chain',
     'research_paper',
     'This paper presents a machine learning approach to supply chain demand forecasting combining time series analysis (ARIMA, Prophet) with gradient boosted decision trees. The hybrid model accounts for seasonal patterns, promotional effects, and external factors including weather and economic indicators. Validation on 3 years of historical data shows 18% improvement in forecast accuracy, reducing inventory carrying costs by $2.3M annually.',
     'ML-based supply chain forecasting with $2.3M annual savings',
     '12345678abcdef01020304050607080901', '/docs/research/supply_chain_ml.pdf', 2700000, 'application/pdf',
     'confidential', 14, 2),

    ('DevOps Maturity Assessment Report',
     'report',
     'Assessment of organizational DevOps maturity across five dimensions: culture, automation, measurement, sharing, and lean practices. Current maturity level 3 of 5. Key findings: strong CI/CD pipelines but gaps in observability and incident management. Recommendations include implementing SRE practices, expanding infrastructure as code coverage from 60% to 95%, and establishing error budgets for all production services.',
     'DevOps maturity at level 3/5 with recommendations for improvement',
     '2345678abcdef0102030405060708090102', '/docs/operations/devops_maturity.pdf', 1200000, 'application/pdf',
     'internal', 1, 7),

    ('Federated Learning for Privacy-Preserving AI',
     'research_paper',
     'Investigation of federated learning approaches for training machine learning models across distributed datasets without centralizing sensitive data. Proposes a novel aggregation algorithm reducing communication overhead by 60% compared to FedAvg while maintaining model accuracy. Addresses challenges including non-IID data distribution, model poisoning attacks, and differential privacy guarantees. Experiments on healthcare and financial datasets demonstrate practical applicability.',
     'Novel federated learning with 60% communication reduction',
     '345678abcdef010203040506070809010203', '/docs/research/federated_learning.pdf', 2900000, 'application/pdf',
     'public', 2, 9),

    ('Incident Management Playbook',
     'technical_doc',
     'Standardized playbook for IT incident management following ITIL best practices. Defines severity levels (P1-P4), escalation procedures, communication templates, post-incident review processes, and SLA requirements. Includes runbooks for common failure scenarios: database failover, network partitions, certificate expiration, and memory leaks. Integrates with PagerDuty, Slack, and Jira for automated incident workflow.',
     'ITIL-based incident management playbook with automated workflows',
     '45678abcdef01020304050607080901020304', '/docs/operations/incident_playbook.md', 540000, 'text/markdown',
     'internal', 1, 7),

    ('Graph Neural Networks for Knowledge Representation',
     'research_paper',
     'This paper explores graph neural network architectures for learning knowledge graph embeddings. We propose a novel attention-based GNN that captures multi-hop relationships and temporal dynamics in entity interactions. Evaluation on standard knowledge graph completion benchmarks (FB15K-237, WN18RR) achieves new state-of-the-art results. The approach is applied to enterprise knowledge graphs demonstrating improved entity resolution and relationship prediction accuracy.',
     'GNN-based knowledge graph embeddings with SOTA benchmark results',
     '5678abcdef0102030405060708090102030405', '/docs/research/gnn_knowledge.pdf', 3400000, 'application/pdf',
     'public', 2, 4),

    ('Compliance Audit Trail Analysis 2025',
     'report',
     'Annual compliance audit report analyzing access patterns, data handling practices, and policy violations across the organization. Key metrics: 99.2% policy compliance rate, 23 minor violations (all resolved), 0 major data breaches. Identified 156 instances of excessive access privileges subsequently remediated. Recommendations include automated access review cycles, enhanced DLP controls, and mandatory annual recertification for users with access to restricted data.',
     '2025 compliance audit: 99.2% compliance, 0 breaches',
     '678abcdef010203040506070809010203040506', '/docs/compliance/audit_2025.pdf', 1800000, 'application/pdf',
     'restricted', 12, 5);

-- ============================================================================
-- DOCUMENT_VERSIONS
-- ============================================================================
INSERT INTO document_versions (document_id, version_number, content, content_hash, change_summary, changed_by) VALUES
    (1, 1, 'Initial draft of transformer architecture paper with preliminary results.', 'v1_hash_001', 'Initial draft', 4),
    (1, 2, 'Revised methodology section and updated experimental results.', 'v1_hash_002', 'Updated methodology and results', 4),
    (2, 1, 'First version of Zero Trust implementation guide.', 'v2_hash_001', 'Initial version', 3),
    (2, 2, 'Added SOC2 and ISO 27001 mapping sections.', 'v2_hash_002', 'Added compliance mapping', 3),
    (2, 3, 'Incorporated reviewer feedback on microsegmentation.', 'v2_hash_003', 'Reviewer feedback incorporated', 3),
    (3, 1, 'Initial cloud migration strategy draft.', 'v3_hash_001', 'Initial draft', 7),
    (5, 1, 'Q3 incident response preliminary report.', 'v5_hash_001', 'Preliminary report', 3),
    (5, 2, 'Final Q3 incident response report with recommendations.', 'v5_hash_002', 'Finalized with recommendations', 3),
    (7, 1, 'Data governance policy first draft.', 'v7_hash_001', 'Initial draft', 5),
    (7, 2, 'Updated with GDPR and CCPA requirements.', 'v7_hash_002', 'Added regulatory requirements', 5);

-- ============================================================================
-- ENTITIES
-- ============================================================================
INSERT INTO entities (name, entity_type, description, canonical_name, confidence) VALUES
    ('Google',              'organization',  'Technology company, major cloud provider and AI research leader',         'Google LLC',               0.980),
    ('Microsoft',           'organization',  'Technology corporation, Azure cloud and enterprise software provider',    'Microsoft Corporation',    0.990),
    ('Amazon Web Services', 'organization',  'Cloud computing platform by Amazon',                                      'AWS',                      0.985),
    ('Kubernetes',          'technology',    'Container orchestration platform',                                         'Kubernetes (K8s)',         0.995),
    ('TensorFlow',          'technology',    'Open-source machine learning framework by Google',                         'TensorFlow',               0.990),
    ('PyTorch',             'technology',    'Open-source ML framework by Meta AI',                                     'PyTorch',                  0.990),
    ('BERT',                'technology',    'Bidirectional Encoder Representations from Transformers',                  'BERT',                     0.985),
    ('GPT',                 'technology',    'Generative Pre-trained Transformer language model family',                 'GPT',                      0.980),
    ('Zero Trust',          'standard',     'Security framework eliminating implicit trust',                             'Zero Trust Architecture',  0.970),
    ('OAuth 2.0',           'standard',     'Open authorization framework for secure API access',                        'OAuth 2.0',                0.990),
    ('Docker',              'technology',    'Container runtime and image format',                                       'Docker',                   0.995),
    ('PostgreSQL',          'technology',    'Open-source relational database management system',                        'PostgreSQL',               0.995),
    ('Istio',               'technology',    'Service mesh for Kubernetes',                                              'Istio',                    0.960),
    ('ArgoCD',              'technology',    'GitOps continuous delivery tool for Kubernetes',                            'ArgoCD',                   0.950),
    ('NIST',                'organization',  'National Institute of Standards and Technology',                           'NIST',                     0.990),
    ('Dr. Sarah Lin',       'person',       'Leading researcher in NLP and knowledge graphs',                            'Sarah Lin',                0.850),
    ('Prof. James Howard',  'person',       'Expert in cybersecurity and zero trust architectures',                      'James Howard',             0.840),
    ('Raj Patel',           'person',       'Cloud architecture specialist',                                             'Raj Patel',                0.830),
    ('Silicon Valley',      'location',     'Technology hub in California, USA',                                         'Silicon Valley, CA',       0.950),
    ('GDPR',                'standard',     'General Data Protection Regulation',                                        'GDPR',                     0.990),
    ('Transformer',         'technology',    'Neural network architecture based on self-attention mechanism',            'Transformer Architecture', 0.985),
    ('Federated Learning',  'technology',    'ML technique training on distributed data without centralization',         'Federated Learning',       0.970),
    ('GraphSAGE',           'technology',    'Inductive graph neural network framework',                                'GraphSAGE',                0.940),
    ('PagerDuty',           'technology',    'Incident management and alerting platform',                               'PagerDuty',                0.960),
    ('Prophet',             'technology',    'Time series forecasting framework by Meta',                               'Prophet',                  0.950);

-- ============================================================================
-- CONCEPTS
-- ============================================================================
INSERT INTO concepts (name, domain, description, taxonomy_id, relevance_score) VALUES
    ('Machine Learning',            'AI',          'Algorithms that improve through experience and data',                    2,  9.500),
    ('Deep Learning',               'AI',          'Neural network architectures with multiple layers',                      5,  9.200),
    ('Natural Language Processing', 'AI',          'Processing and understanding human language',                            6,  9.000),
    ('Knowledge Graphs',            'AI',          'Structured representation of real-world entities and relationships',     2,  8.800),
    ('Cybersecurity',               'Security',    'Protection of systems, networks, and data from threats',                 3,  9.100),
    ('Cloud Architecture',          'Infrastructure', 'Design patterns for cloud-based systems',                            4,  8.500),
    ('DevOps',                      'Operations',  'Practices combining development and IT operations',                     1,  8.000),
    ('Data Governance',             'Compliance',  'Management and control of data assets',                                 12, 7.500),
    ('Transfer Learning',           'AI',          'Reusing pre-trained models for new tasks',                              2,  8.200),
    ('Container Orchestration',     'Infrastructure', 'Managing containerized application deployment',                      4,  8.100),
    ('API Design',                  'Engineering', 'Design patterns for application programming interfaces',                1,  7.800),
    ('Incident Management',         'Operations',  'Processes for handling IT incidents',                                   1,  7.200),
    ('Supply Chain Analytics',      'Business',    'Data-driven optimization of supply chain operations',                   14, 7.000),
    ('Privacy-Preserving AI',       'AI',          'ML techniques that protect data privacy',                               2,  8.600),
    ('Graph Neural Networks',       'AI',          'Neural networks operating on graph-structured data',                    5,  8.400),
    ('Microservices',               'Engineering', 'Architectural style decomposing applications into small services',      1,  8.300),
    ('Compliance',                  'Governance',  'Adherence to regulations and organizational policies',                  12, 7.600),
    ('Predictive Analytics',        'Analytics',   'Using data and ML to predict future outcomes',                          14, 7.900);

-- ============================================================================
-- TAGS
-- ============================================================================
INSERT INTO tags (name, category) VALUES
    ('machine-learning',    'technology'),
    ('security',            'technology'),
    ('cloud',               'infrastructure'),
    ('research',            'type'),
    ('best-practices',      'methodology'),
    ('compliance',          'governance'),
    ('deep-learning',       'technology'),
    ('kubernetes',          'infrastructure'),
    ('nlp',                 'technology'),
    ('devops',              'methodology'),
    ('incident-response',   'operations'),
    ('data-governance',     'governance'),
    ('api',                 'technology'),
    ('graph-neural-networks','technology'),
    ('federated-learning',  'technology'),
    ('supply-chain',        'business'),
    ('optimization',        'methodology'),
    ('privacy',             'governance');

-- ============================================================================
-- RELATIONS (Entity-to-Entity Relationships)
-- ============================================================================
INSERT INTO relations (source_entity_id, target_entity_id, relation_type, strength, description, source_document_id) VALUES
    (5,  1,  'developed_by',       0.950, 'TensorFlow is developed by Google',                             4),
    (6,  2,  'related_to',         0.700, 'PyTorch is associated with Meta but competes in Microsoft space',4),
    (7,  1,  'developed_by',       0.950, 'BERT was developed by Google Research',                         1),
    (4,  1,  'related_to',         0.800, 'Google is a major contributor to Kubernetes',                    6),
    (4,  11, 'depends_on',         0.900, 'Kubernetes orchestrates Docker containers',                      6),
    (13, 4,  'part_of',            0.850, 'Istio is a service mesh for Kubernetes',                         6),
    (14, 4,  'related_to',         0.800, 'ArgoCD provides GitOps for Kubernetes',                          6),
    (9,  15, 'related_to',         0.750, 'Zero Trust references NIST frameworks',                          2),
    (3,  1,  'competitor_of',      0.850, 'AWS competes with Google Cloud',                                 3),
    (3,  2,  'competitor_of',      0.850, 'AWS competes with Microsoft Azure',                              3),
    (8,  21, 'successor_of',       0.900, 'GPT is based on the Transformer architecture',                   1),
    (7,  21, 'uses',               0.950, 'BERT uses the Transformer architecture',                          1),
    (16, 21, 'uses',               0.800, 'Dr. Sarah Lin works with Transformer models',                    1),
    (17, 9,  'uses',               0.850, 'Prof. Howard specializes in Zero Trust',                          2),
    (18, 3,  'uses',               0.800, 'Raj Patel specializes in AWS architecture',                       3),
    (22, 5,  'uses',               0.750, 'Federated Learning can use TensorFlow',                           12),
    (22, 6,  'uses',               0.750, 'Federated Learning can use PyTorch',                              12),
    (23, 22, 'related_to',         0.700, 'GraphSAGE relates to federated graph learning',                   14),
    (16, 1,  'collaborates_with',  0.650, 'Dr. Lin collaborates with Google on NLP research',                1),
    (25, 6,  'related_to',         0.600, 'Prophet is related to PyTorch ecosystem',                         10);

-- ============================================================================
-- DOCUMENT_ENTITIES
-- ============================================================================
INSERT INTO document_entities (document_id, entity_id, relevance, mention_count, first_occurrence) VALUES
    (1,  21, 0.950,  12, 15),   -- Transformer in doc 1
    (1,  7,  0.850,   8, 45),   -- BERT in doc 1
    (1,  8,  0.800,   5, 120),  -- GPT in doc 1
    (1,  16, 0.700,   3, 200),  -- Dr. Sarah Lin in doc 1
    (2,  9,  0.950,  18, 10),   -- Zero Trust in doc 2
    (2,  15, 0.800,   6, 350),  -- NIST in doc 2
    (2,  17, 0.650,   2, 500),  -- Prof. Howard in doc 2
    (2,  20, 0.700,   4, 600),  -- GDPR in doc 2
    (3,  3,  0.900,  10, 30),   -- AWS in doc 3
    (3,  2,  0.850,   8, 60),   -- Microsoft in doc 3
    (3,  4,  0.750,   5, 300),  -- Kubernetes in doc 3
    (3,  18, 0.600,   2, 400),  -- Raj Patel in doc 3
    (4,  5,  0.800,   6, 100),  -- TensorFlow in doc 4
    (4,  6,  0.800,   6, 110),  -- PyTorch in doc 4
    (5,  9,  0.600,   3, 250),  -- Zero Trust mentioned in doc 5
    (6,  4,  0.950,  15, 5),    -- Kubernetes in doc 6
    (6,  11, 0.850,   8, 20),   -- Docker in doc 6
    (6,  13, 0.800,   6, 150),  -- Istio in doc 6
    (6,  14, 0.700,   4, 400),  -- ArgoCD in doc 6
    (7,  20, 0.900,  10, 50),   -- GDPR in doc 7
    (8,  5,  0.700,   4, 200),  -- TensorFlow in doc 8
    (8,  6,  0.700,   4, 210),  -- PyTorch in doc 8
    (9,  10, 0.850,   7, 30),   -- OAuth 2.0 in doc 9
    (10, 25, 0.800,   5, 150),  -- Prophet in doc 10
    (12, 22, 0.950,  14, 10),   -- Federated Learning in doc 12
    (13, 24, 0.800,   5, 200),  -- PagerDuty in doc 13
    (14, 23, 0.850,   8, 100),  -- GraphSAGE in doc 14
    (14, 21, 0.750,   4, 50);   -- Transformer in doc 14

-- ============================================================================
-- DOCUMENT_TAGS
-- ============================================================================
INSERT INTO document_tags (document_id, tag_id, tagged_by) VALUES
    (1,  1,  4),   -- machine-learning
    (1,  9,  4),   -- nlp
    (1,  4,  4),   -- research
    (1,  7,  4),   -- deep-learning
    (2,  2,  3),   -- security
    (2,  5,  3),   -- best-practices
    (2,  6,  3),   -- compliance
    (3,  3,  7),   -- cloud
    (3,  5,  7),   -- best-practices
    (4,  1,  2),   -- machine-learning
    (4,  5,  2),   -- best-practices
    (4,  10, 2),   -- devops
    (5,  2,  3),   -- security
    (5,  11, 3),   -- incident-response
    (6,  8,  6),   -- kubernetes
    (6,  3,  6),   -- cloud
    (6,  10, 6),   -- devops
    (7,  12, 5),   -- data-governance
    (7,  6,  5),   -- compliance
    (8,  7,  4),   -- deep-learning
    (8,  4,  4),   -- research
    (8,  17, 4),   -- optimization
    (9,  13, 1),   -- api
    (9,  5,  1),   -- best-practices
    (10, 1,  2),   -- machine-learning
    (10, 16, 2),   -- supply-chain
    (10, 4,  2),   -- research
    (11, 10, 7),   -- devops
    (12, 15, 9),   -- federated-learning
    (12, 18, 9),   -- privacy
    (12, 4,  9),   -- research
    (13, 11, 7),   -- incident-response
    (13, 5,  7),   -- best-practices
    (14, 14, 4),   -- graph-neural-networks
    (14, 7,  4),   -- deep-learning
    (14, 4,  4),   -- research
    (15, 6,  5),   -- compliance
    (15, 12, 5);   -- data-governance

-- ============================================================================
-- CONCEPT_HIERARCHY
-- ============================================================================
INSERT INTO concept_hierarchy (parent_concept_id, child_concept_id, relationship_type) VALUES
    (1,  2,  'is_parent_of'),           -- ML > Deep Learning
    (1,  9,  'is_specialization_of'),   -- ML > Transfer Learning
    (1,  18, 'is_specialization_of'),   -- ML > Predictive Analytics
    (2,  3,  'is_parent_of'),           -- Deep Learning > NLP
    (2,  15, 'is_parent_of'),           -- Deep Learning > Graph Neural Networks
    (1,  14, 'is_specialization_of'),   -- ML > Privacy-Preserving AI
    (1,  4,  'is_parent_of'),           -- ML > Knowledge Graphs
    (6,  10, 'is_parent_of'),           -- Cloud Architecture > Container Orchestration
    (6,  16, 'is_parent_of'),           -- Cloud Architecture > Microservices
    (10, 7,  'is_prerequisite_of'),     -- Container Orchestration prerequisite for DevOps
    (5,  8,  'is_parent_of'),           -- Cybersecurity > Data Governance
    (8,  17, 'is_parent_of'),           -- Data Governance > Compliance
    (7,  12, 'is_parent_of');           -- DevOps > Incident Management

-- ============================================================================
-- ENTITY_CONCEPTS
-- ============================================================================
INSERT INTO entity_concepts (entity_id, concept_id, relevance_score) VALUES
    (5,  1,  0.950),   -- TensorFlow ↔ Machine Learning
    (5,  2,  0.900),   -- TensorFlow ↔ Deep Learning
    (6,  1,  0.950),   -- PyTorch ↔ Machine Learning
    (6,  2,  0.900),   -- PyTorch ↔ Deep Learning
    (7,  3,  0.950),   -- BERT ↔ NLP
    (7,  9,  0.850),   -- BERT ↔ Transfer Learning
    (8,  3,  0.930),   -- GPT ↔ NLP
    (21, 2,  0.950),   -- Transformer ↔ Deep Learning
    (21, 3,  0.900),   -- Transformer ↔ NLP
    (4,  10, 0.950),   -- Kubernetes ↔ Container Orchestration
    (4,  6,  0.800),   -- Kubernetes ↔ Cloud Architecture
    (11, 10, 0.850),   -- Docker ↔ Container Orchestration
    (9,  5,  0.950),   -- Zero Trust ↔ Cybersecurity
    (20, 17, 0.900),   -- GDPR ↔ Compliance
    (20, 8,  0.850),   -- GDPR ↔ Data Governance
    (22, 14, 0.950),   -- Federated Learning ↔ Privacy-Preserving AI
    (22, 1,  0.850),   -- Federated Learning ↔ ML
    (23, 15, 0.950),   -- GraphSAGE ↔ Graph Neural Networks
    (23, 4,  0.800),   -- GraphSAGE ↔ Knowledge Graphs
    (25, 18, 0.800),   -- Prophet ↔ Predictive Analytics
    (24, 12, 0.850),   -- PagerDuty ↔ Incident Management
    (12, 8,  0.700);   -- PostgreSQL ↔ Data Governance

-- ============================================================================
-- DOCUMENT_CONCEPTS
-- ============================================================================
INSERT INTO document_concepts (document_id, concept_id, relevance_score, extracted_by) VALUES
    (1,  3,  0.950, 'ai'),      -- Transformer paper ↔ NLP
    (1,  9,  0.850, 'ai'),      -- Transformer paper ↔ Transfer Learning
    (1,  2,  0.800, 'ai'),      -- Transformer paper ↔ Deep Learning
    (1,  4,  0.700, 'ai'),      -- Transformer paper ↔ Knowledge Graphs
    (2,  5,  0.950, 'manual'),  -- Zero Trust guide ↔ Cybersecurity
    (2,  17, 0.800, 'manual'),  -- Zero Trust guide ↔ Compliance
    (3,  6,  0.950, 'system'),  -- Cloud migration ↔ Cloud Architecture
    (3,  10, 0.700, 'system'),  -- Cloud migration ↔ Container Orchestration
    (4,  1,  0.950, 'ai'),      -- ML Pipeline ↔ Machine Learning
    (4,  7,  0.700, 'ai'),      -- ML Pipeline ↔ DevOps
    (5,  5,  0.900, 'system'),  -- Incident report ↔ Cybersecurity
    (5,  12, 0.750, 'system'),  -- Incident report ↔ Incident Management
    (6,  10, 0.950, 'system'),  -- K8s patterns ↔ Container Orchestration
    (6,  16, 0.800, 'system'),  -- K8s patterns ↔ Microservices
    (6,  7,  0.750, 'system'),  -- K8s patterns ↔ DevOps
    (7,  8,  0.950, 'manual'),  -- Data governance ↔ Data Governance
    (7,  17, 0.900, 'manual'),  -- Data governance ↔ Compliance
    (8,  2,  0.950, 'ai'),      -- NN optimization ↔ Deep Learning
    (8,  1,  0.850, 'ai'),      -- NN optimization ↔ ML
    (9,  11, 0.900, 'system'),  -- API gateway ↔ API Design
    (9,  16, 0.750, 'system'),  -- API gateway ↔ Microservices
    (10, 18, 0.950, 'ai'),      -- Supply chain ↔ Predictive Analytics
    (10, 1,  0.800, 'ai'),      -- Supply chain ↔ ML
    (10, 13, 0.850, 'ai'),      -- Supply chain ↔ Supply Chain Analytics
    (11, 7,  0.950, 'system'),  -- DevOps maturity ↔ DevOps
    (12, 14, 0.950, 'ai'),      -- Federated learning ↔ Privacy-Preserving AI
    (12, 1,  0.800, 'ai'),      -- Federated learning ↔ ML
    (13, 12, 0.950, 'system'),  -- Incident playbook ↔ Incident Management
    (13, 7,  0.750, 'system'),  -- Incident playbook ↔ DevOps
    (14, 15, 0.950, 'ai'),      -- GNN paper ↔ Graph Neural Networks
    (14, 4,  0.900, 'ai'),      -- GNN paper ↔ Knowledge Graphs
    (14, 2,  0.800, 'ai'),      -- GNN paper ↔ Deep Learning
    (15, 17, 0.950, 'manual'),  -- Compliance audit ↔ Compliance
    (15, 8,  0.850, 'manual');  -- Compliance audit ↔ Data Governance

-- ============================================================================
-- EMBEDDINGS (sample vectors — reduced dimensionality for illustration)
-- ============================================================================
INSERT INTO embeddings (source_type, source_id, model_name, vector, dimensions) VALUES
    ('document', 1,  'text-embedding-ada-002', ARRAY[0.12, -0.34, 0.56, 0.78, -0.11, 0.44, 0.67, -0.23], 8),
    ('document', 2,  'text-embedding-ada-002', ARRAY[-0.15, 0.42, -0.33, 0.61, 0.28, -0.52, 0.19, 0.37], 8),
    ('document', 3,  'text-embedding-ada-002', ARRAY[0.08, 0.55, -0.22, 0.41, -0.18, 0.63, -0.31, 0.49], 8),
    ('document', 4,  'text-embedding-ada-002', ARRAY[0.22, -0.41, 0.63, 0.55, -0.19, 0.38, 0.71, -0.14], 8),
    ('document', 5,  'text-embedding-ada-002', ARRAY[-0.28, 0.37, -0.45, 0.52, 0.33, -0.61, 0.15, 0.44], 8),
    ('entity',   21, 'text-embedding-ada-002', ARRAY[0.18, -0.38, 0.59, 0.72, -0.15, 0.41, 0.65, -0.20], 8),
    ('entity',   4,  'text-embedding-ada-002', ARRAY[0.05, 0.48, -0.25, 0.38, -0.12, 0.58, -0.35, 0.42], 8),
    ('concept',  1,  'text-embedding-ada-002', ARRAY[0.20, -0.36, 0.61, 0.68, -0.13, 0.40, 0.69, -0.17], 8),
    ('concept',  5,  'text-embedding-ada-002', ARRAY[-0.22, 0.40, -0.38, 0.57, 0.30, -0.55, 0.17, 0.40], 8),
    ('concept',  6,  'text-embedding-ada-002', ARRAY[0.06, 0.52, -0.20, 0.42, -0.16, 0.60, -0.28, 0.46], 8);

-- ============================================================================
-- QUERY_LOGS
-- ============================================================================
INSERT INTO query_logs (user_id, query_text, query_type, results_count, execution_ms) VALUES
    (8,  'machine learning best practices',         'keyword_search',    12, 45),
    (8,  'find experts in cybersecurity',            'graph_traversal',    3, 120),
    (10, 'kubernetes deployment patterns',           'keyword_search',     5, 38),
    (2,  'related concepts to deep learning',        'graph_traversal',    8, 95),
    (4,  'transformer architecture papers',          'semantic_search',    4, 210),
    (5,  'restricted document access last 30 days',  'analytics',          7, 150),
    (1,  'user role assignments report',             'admin',              15, 65),
    (9,  'federated learning privacy research',      'semantic_search',    3, 185),
    (3,  'security incident trends 2025',            'analytics',          6, 88),
    (7,  'devops maturity cloud migration',          'keyword_search',     4, 52);

-- ============================================================================
-- AUDIT_LOGS
-- ============================================================================
INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES
    (8,  'view',           'document',  2,    'Viewed confidential Zero Trust guide',              '192.168.1.100'),
    (3,  'view',           'document',  5,    'Viewed restricted Q3 incident report',              '192.168.1.101'),
    (5,  'view',           'document',  5,    'Compliance review of incident report',              '192.168.1.102'),
    (10, 'access_denied',  'document',  5,    'Consumer attempted to access restricted document',  '192.168.1.103'),
    (1,  'create',         'user',      10,   'Created new user account for David Brown',          '192.168.1.104'),
    (1,  'update',         'role',      NULL, 'Updated contributor role permissions',               '192.168.1.104'),
    (5,  'export',         'document',  15,   'Exported compliance audit report',                   '192.168.1.102'),
    (3,  'update',         'document',  2,    'Updated Zero Trust guide v3',                        '192.168.1.101'),
    (4,  'create',         'document',  1,    'Uploaded transformer architecture paper',             '192.168.1.105'),
    (2,  'view',           'document',  10,   'Viewed confidential supply chain analysis',           '192.168.1.106'),
    (7,  'create',         'document',  3,    'Uploaded cloud migration strategy',                   '192.168.1.107'),
    (5,  'view',           'document',  15,   'Annual compliance audit review',                      '192.168.1.102'),
    (1,  'login',          'system',    NULL, 'Admin login',                                         '192.168.1.104'),
    (5,  'login',          'system',    NULL, 'Compliance officer login',                             '192.168.1.102'),
    (10, 'login',          'system',    NULL, 'User login',                                           '192.168.1.103');

-- ============================================================================
-- END OF SAMPLE DATA
-- ============================================================================
