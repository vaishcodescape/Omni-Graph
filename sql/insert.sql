SET search_path TO omnigraph;

TRUNCATE TABLE
    audit_logs, query_logs, embeddings,
    document_concepts, entity_concepts, concept_hierarchy,
    document_tags, document_entities, relations,
    document_versions, documents, tags, concepts,
    entities, taxonomy, access_policies, user_roles, users, roles
RESTART IDENTITY CASCADE;

-- roles
INSERT INTO roles (role_name, description, permissions) VALUES
  ('admin',
   'Full platform administrator with unrestricted access',
   ARRAY['view_graph','manage_roles','manage_documents','manage_users',
         'view_audit','run_analytics','export_data','manage_taxonomy']),
  ('contributor',
   'Knowledge worker who uploads and tags documents',
   ARRAY['view_graph','manage_documents','tag_documents','run_analytics']),
  ('consumer',
   'Read-only analyst; can search and read permitted documents',
   ARRAY['view_graph','run_analytics']),
  ('compliance',
   'Compliance officer with access to restricted audit and sensitive content',
   ARRAY['view_audit','view_sensitive','export_data','run_analytics']);


-- users
INSERT INTO users (username, email, full_name, department, title, password_hash) VALUES
  ('alice.morgan',  'alice.morgan@nexacorp.io',  'Alice Morgan',  'Engineering',       'Principal Engineer',     '$2b$12$AAAAAAAAAAAAAAAAAAAAAAAA'),
  ('ben.okafor',    'ben.okafor@nexacorp.io',    'Ben Okafor',    'Research',          'Research Scientist',     '$2b$12$BBBBBBBBBBBBBBBBBBBBBBBB'),
  ('carmen.diaz',   'carmen.diaz@nexacorp.io',   'Carmen Diaz',   'Legal & Compliance','Compliance Lead',        '$2b$12$CCCCCCCCCCCCCCCCCCCCCCCC'),
  ('derek.tan',     'derek.tan@nexacorp.io',     'Derek Tan',     'DevOps',            'Senior DevOps Engineer', '$2b$12$DDDDDDDDDDDDDDDDDDDDDDDD'),
  ('elena.kovac',   'elena.kovac@nexacorp.io',   'Elena Kovac',   'Research',          'ML Engineer',            '$2b$12$EEEEEEEEEEEEEEEEEEEEEEEE'),
  ('frank.adeyemi', 'frank.adeyemi@nexacorp.io', 'Frank Adeyemi', 'Engineering',       'Backend Developer',      '$2b$12$FFFFFFFFFFFFFFFFFFFFFFFF'),
  ('grace.huang',   'grace.huang@nexacorp.io',   'Grace Huang',   'Product',           'Product Manager',        '$2b$12$GGGGGGGGGGGGGGGGGGGGGGGG'),
  ('hiro.yamamoto', 'hiro.yamamoto@nexacorp.io', 'Hiro Yamamoto', 'Security',          'Security Analyst',       '$2b$12$HHHHHHHHHHHHHHHHHHHHHHHH');


-- assign roles to users
INSERT INTO user_roles (user_id, role_id, assigned_by) VALUES
  (1, 1, 1),
  (2, 2, 1),
  (3, 4, 1),
  (4, 2, 1),
  (5, 2, 1),
  (6, 2, 1),
  (7, 3, 1),
  (8, 3, 1),
  (8, 4, 1);


-- access policies per role and sensitivity level
INSERT INTO access_policies (role_id, resource_type, sensitivity_level, can_read, can_write, can_delete) VALUES
  (1, 'document',  'public',       TRUE,  TRUE,  TRUE),
  (1, 'document',  'internal',     TRUE,  TRUE,  TRUE),
  (1, 'document',  'confidential', TRUE,  TRUE,  TRUE),
  (1, 'document',  'restricted',   TRUE,  TRUE,  TRUE),
  (1, 'entity',    'public',       TRUE,  TRUE,  TRUE),
  (1, 'concept',   'public',       TRUE,  TRUE,  TRUE),
  (1, 'audit_log', 'public',       TRUE,  FALSE, FALSE),

  (2, 'document',  'public',       TRUE,  TRUE,  FALSE),
  (2, 'document',  'internal',     TRUE,  TRUE,  FALSE),
  (2, 'document',  'confidential', FALSE, FALSE, FALSE),
  (2, 'document',  'restricted',   FALSE, FALSE, FALSE),
  (2, 'entity',    'public',       TRUE,  TRUE,  FALSE),
  (2, 'concept',   'public',       TRUE,  TRUE,  FALSE),

  (3, 'document',  'public',       TRUE,  FALSE, FALSE),
  (3, 'document',  'internal',     TRUE,  FALSE, FALSE),
  (3, 'document',  'confidential', FALSE, FALSE, FALSE),
  (3, 'document',  'restricted',   FALSE, FALSE, FALSE),
  (3, 'entity',    'public',       TRUE,  FALSE, FALSE),
  (3, 'concept',   'public',       TRUE,  FALSE, FALSE),

  (4, 'document',  'public',       TRUE,  FALSE, FALSE),
  (4, 'document',  'internal',     TRUE,  FALSE, FALSE),
  (4, 'document',  'confidential', TRUE,  FALSE, FALSE),
  (4, 'document',  'restricted',   TRUE,  FALSE, FALSE),
  (4, 'audit_log', 'public',       TRUE,  FALSE, FALSE);


-- taxonomy tree
INSERT INTO taxonomy (name, description, parent_id, level, domain) VALUES
  ('Technology',          'Root: all technology topics',                    NULL, 0, 'Technology'),
  ('Artificial Intelligence', 'Machine learning, NLP, and AI sub-topics',  1,    1, 'Technology'),
  ('Infrastructure',      'Cloud, DevOps, and systems topics',              1,    1, 'Technology'),
  ('Security',            'Cybersecurity and compliance topics',            1,    1, 'Technology'),
  ('Business',            'Root: business and operations topics',           NULL, 0, 'Business'),
  ('Compliance',          'Regulatory and legal compliance',                5,    1, 'Business'),
  ('Operations',          'Business operations and logistics',              5,    1, 'Business'),
  ('Research',            'Root: research and academic topics',             NULL, 0, 'Research'),
  ('Deep Learning',       'Neural network architectures and training',      2,    2, 'Technology'),
  ('Cloud Computing',     'Public and hybrid cloud platforms',              3,    2, 'Technology'),
  ('Containerisation',    'Container orchestration and packaging',          3,    2, 'Technology');


-- documents
INSERT INTO documents (title, source_type, content, summary, content_hash,
                       sensitivity_level, taxonomy_id, uploaded_by, mime_type) VALUES

  ('Transformer Architectures in Large-Scale NLP',
   'research_paper',
   'This paper surveys transformer-based architectures including BERT, GPT, and T5. '
   'We examine attention mechanisms, positional encoding, and fine-tuning strategies '
   'for downstream tasks. TensorFlow and PyTorch are used for benchmarking. '
   'Results show that deep learning models outperform classical baselines by 18%.',
   'Survey of transformer architectures and their applications in NLP.',
   'd1a2b3c4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2',
   'public', 9, 2, 'text/plain'),

  ('Kubernetes Cluster Deployment Runbook',
   'technical_doc',
   'This runbook describes the procedure for deploying and scaling Kubernetes clusters '
   'on AWS EKS. Prerequisites include Docker, Helm, and Terraform. '
   'The deployment pipeline uses ArgoCD for GitOps-based continuous delivery. '
   'All clusters are monitored via Prometheus and Grafana dashboards.',
   'Operational runbook for EKS cluster deployment using Helm and ArgoCD.',
   'b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3',
   'internal', 11, 4, 'text/plain'),

  ('Q4 2025 Security Incident Report',
   'report',
   'This report documents three security incidents observed in Q4 2025. '
   'Incident 1: Brute-force attempt on the OAuth 2.0 authentication gateway. '
   'Incident 2: Misconfigured S3 bucket exposed internal API keys for 4 hours. '
   'Incident 3: Suspicious lateral movement detected in the production VPC. '
   'NIST 800-53 controls were applied as remediation measures.',
   'Internal security incident summary for Q4 2025 with remediation tracking.',
   'c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4',
   'confidential', 4, 8, 'text/plain'),

  ('Annual GDPR Compliance Assessment 2025',
   'report',
   'This restricted document contains the full GDPR data processing audit results. '
   'Findings: 3 data subject access requests were unfulfilled beyond the 30-day limit. '
   'Data residency for EU customers is compliant with Article 44-49 transfer rules. '
   'DPO recommendations: implement automated DSAR workflows by Q2 2026.',
   'Full GDPR compliance assessment with findings and DPO action items.',
   'd4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5',
   'restricted', 6, 3, 'text/plain'),

  ('Re: PyTorch Model Training Pipeline Migration',
   'email',
   'Hi team, following up on the migration of our CNN training pipeline from TensorFlow '
   'to PyTorch. Elena has completed the initial port and benchmarks show a 12% speedup. '
   'Next steps: integrate MLflow for experiment tracking, update CI/CD in Jenkins. '
   'Please review the draft PR before end of sprint.',
   'Internal thread on ML pipeline migration from TensorFlow to PyTorch.',
   'e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6',
   'internal', 2, 5, 'text/plain'),

  ('Introduction to Zero Trust Security Architecture',
   'presentation',
   'This presentation introduces Zero Trust principles for enterprise networks. '
   'Key pillars: verify explicitly, use least privilege access, and assume breach. '
   'Tools discussed: Azure AD Conditional Access, OAuth 2.0, and NIST 800-207 guidelines. '
   'Audience: engineering and operations teams onboarding in Q1 2026.',
   'Public-facing slide deck introducing Zero Trust and least-privilege principles.',
   'f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7',
   'public', 4, 8, 'text/plain'),

  ('OmniGraph Core: Graph Builder Module',
   'code_repository',
   'Python module implementing the KnowledgeGraphBuilder class. '
   'Provides entity node CRUD, typed relationship management, taxonomy tree operations, '
   'concept hierarchy links, and recursive neighborhood traversal up to N hops. '
   'Backed by PostgreSQL 14 with recursive CTEs. Uses psycopg2 for DB access.',
   'Source code documentation for the OmniGraph graph builder Python module.',
   'a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8',
   'internal', 1, 1, 'text/plain'),

  ('Federated Learning for On-Device Model Personalisation',
   'research_paper',
   'This paper proposes a federated learning framework for personalising neural network '
   'models on edge devices without transmitting raw user data. '
   'We evaluate on IoT sensor datasets. PyTorch and CUDA are used for GPU acceleration. '
   'Results show 94% model accuracy with 60% reduction in data egress costs. '
   'Methodology follows GDPR-compatible data minimisation principles.',
   'Research paper on privacy-preserving federated learning for edge AI.',
   'b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9',
   'confidential', 9, 2, 'text/plain'),

  ('TICKET-4821: Helm Chart Rollback Failure on EKS v1.28',
   'support_ticket',
   'Issue: Helm rollback fails silently on EKS clusters running Kubernetes v1.28. '
   'Root cause: deprecated API version in ArgoCD application manifest (apps/v1beta1). '
   'Resolution: Updated manifest to apps/v1 and re-ran helm upgrade --atomic. '
   'Status: Resolved. Reference: AWS EKS documentation and Helm GitHub issue #9123.',
   'Support ticket for Helm rollback failure on Kubernetes v1.28 / EKS.',
   'c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0',
   'public', 11, 4, 'text/plain'),

  ('Production API Gateway Access Log — January 2026',
   'log',
   'Aggregated access log entries for the production API gateway for January 2026. '
   'Total requests: 4,812,334. Error rate: 0.3%. Top endpoints: /api/search (38%), '
   '/api/ingest (22%), /api/agent/ask (18%). Peak traffic: 2026-01-15 14:30 UTC. '
   'No anomalous patterns detected. OAuth 2.0 token validation success rate: 99.97%.',
   'Monthly access log summary for the production API gateway — January 2026.',
   'd0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1',
   'internal', 3, 1, 'text/plain');


-- version history for select documents
INSERT INTO document_versions (document_id, version_number, content, content_hash,
                                change_summary, changed_by) VALUES
  (1, 1,
   'Original submission draft for Transformer Architectures survey.',
   '1111111111111111111111111111111111111111111111111111111111111111',
   'Initial draft upload', 2),

  (3, 1,
   'Preliminary incident summary — data pending forensic analysis.',
   '2222222222222222222222222222222222222222222222222222222222222222',
   'Preliminary draft before forensic completion', 8),

  (3, 2,
   'Updated with full remediation tracking from NIST controls review.',
   '3333333333333333333333333333333333333333333333333333333333333333',
   'Added NIST 800-53 remediation detail', 8),

  (4, 1,
   'First draft GDPR assessment — DPO findings pending.',
   '4444444444444444444444444444444444444444444444444444444444444444',
   'Initial draft — DPO review pending', 3);


-- entities (technologies, standards, people, orgs, locations)
INSERT INTO entities (name, entity_type, description, canonical_name, confidence) VALUES
  ('Kubernetes',         'technology',   'Open-source container orchestration system',   'Kubernetes',     0.990),
  ('Docker',             'technology',   'Container runtime and image format',            'Docker',         0.985),
  ('PyTorch',            'technology',   'Open-source deep learning framework by Meta',   'PyTorch',        0.992),
  ('TensorFlow',         'technology',   'Google open-source ML framework',               'TensorFlow',     0.988),
  ('PostgreSQL',         'technology',   'Open-source relational database system',        'PostgreSQL',     0.982),
  ('Helm',               'technology',   'Package manager for Kubernetes',                'Helm',           0.975),
  ('ArgoCD',             'technology',   'GitOps-based continuous delivery for K8s',     'Argo CD',        0.970),
  ('OAuth 2.0',          'standard',     'Industry-standard authorization protocol',      'OAuth 2.0',      0.995),
  ('GDPR',               'standard',     'EU General Data Protection Regulation',         'GDPR',           0.998),
  ('NIST 800-53',        'standard',     'NIST security and privacy control catalogue',   'NIST 800-53',    0.990),
  ('Google',             'organization', 'Technology company behind TensorFlow, GCP',    'Google LLC',     0.995),
  ('Amazon Web Services','organization', 'Cloud computing division of Amazon',            'AWS',            0.993),
  ('Dr. Elena Kovac',    'person',       'ML Engineer and federated learning researcher', 'Elena Kovac',    0.920),
  ('Dr. Ben Okafor',     'person',       'Research Scientist specialising in NLP',        'Ben Okafor',     0.905),
  ('European Union',     'location',     'Political and economic union of 27 states',     'European Union', 0.980);


-- concepts and knowledge domains
INSERT INTO concepts (name, domain, description, taxonomy_id, relevance_score) VALUES
  ('Machine Learning',          'AI',             'Statistical learning from data to make predictions',        2,  0.950),
  ('Deep Learning',             'AI',             'Neural network models with multiple hidden layers',          9,  0.920),
  ('Federated Learning',        'AI',             'Privacy-preserving distributed model training on edge',     9,  0.880),
  ('Zero Trust',                'Security',       'Security model assuming no implicit trust on any network',   4,  0.870),
  ('Data Privacy',              'Compliance',     'Principles and regulations governing personal data use',     6,  0.900),
  ('Container Orchestration',   'Infrastructure', 'Automated deployment and management of containers',         11, 0.860),
  ('CI/CD',                     'Operations',     'Continuous integration and delivery of software',            7,  0.840),
  ('Natural Language Processing','AI',            'Computational techniques for understanding human language', 2,  0.910);


-- tags
INSERT INTO tags (name, category) VALUES
  ('nlp',           'AI'),
  ('kubernetes',    'Infrastructure'),
  ('security',      'Security'),
  ('gdpr',          'Compliance'),
  ('deep-learning', 'AI'),
  ('federated',     'AI'),
  ('devops',        'Operations'),
  ('research',      'Research');


-- entity relationships
INSERT INTO relations (source_entity_id, target_entity_id, relation_type,
                       strength, description, source_document_id) VALUES
  (1,  2,  'depends_on',        0.950, 'Kubernetes uses Docker as the default container runtime',        2),
  (6,  1,  'manages',           0.900, 'Helm manages Kubernetes application deployments via charts',     2),
  (7,  1,  'depends_on',        0.920, 'Argo CD orchestrates deployments on Kubernetes clusters',        2),
  (4,  11, 'developed_by',      0.998, 'TensorFlow was created and open-sourced by Google Brain',       1),
  (3,  4,  'collaborates_with', 0.750, 'PyTorch and TensorFlow are compared side-by-side in benchmarks',1),
  (1,  12, 'uses',              0.870, 'Kubernetes clusters deployed on Amazon EKS (AWS)',               2),
  (9,  15, 'located_in',        0.999, 'GDPR is a regulation of the European Union',                    4),
  (13, 3,  'contributes_to',    0.800, 'Dr. Kovac contributed federated learning experiments in PyTorch',8),
  (14, 4,  'uses',              0.820, 'Dr. Okafor uses TensorFlow for NLP model experiments',          1),
  (10, 9,  'part_of',           0.700, 'NIST 800-53 controls overlap with GDPR compliance requirements', 4);


-- which entities appear in which documents
INSERT INTO document_entities (document_id, entity_id, relevance, mention_count, first_occurrence) VALUES
  (1,  3,  0.920, 4, 120),
  (1,  4,  0.910, 5,  85),
  (1,  11, 0.750, 2, 200),
  (1,  14, 0.880, 3,  40),

  (2,  1,  0.990, 8,  10),
  (2,  2,  0.870, 4,  55),
  (2,  6,  0.880, 5,  80),
  (2,  7,  0.860, 4, 110),
  (2,  12, 0.780, 3, 160),

  (3,  8,  0.940, 4,  30),
  (3,  10, 0.830, 3, 190),
  (3,  12, 0.700, 2, 250),

  (4,  9,  0.995, 9,   5),
  (4,  15, 0.890, 4,  70),

  (5,  3,  0.880, 5,  15),
  (5,  4,  0.810, 3,  60),
  (5,  13, 0.900, 4,  20),

  (6,  8,  0.910, 5,  45),
  (6,  10, 0.840, 3, 200),

  (8,  3,  0.950, 7,  50),
  (8,  9,  0.820, 4, 320),
  (8,  13, 0.960, 6,  25),
  (8,  15, 0.730, 2, 340),

  (9,  1,  0.910, 5,  20),
  (9,  6,  0.940, 6,   8),
  (9,  7,  0.890, 4,  90),

  (10, 8,  0.860, 3, 410);


-- document tagging
INSERT INTO document_tags (document_id, tag_id, tagged_by) VALUES
  (1,  1, 2),
  (1,  5, 2),
  (1,  8, 2),
  (2,  2, 4),
  (2,  7, 4),
  (3,  3, 8),
  (4,  4, 3),
  (4,  3, 3),
  (5,  5, 5),
  (5,  8, 5),
  (6,  3, 8),
  (7,  2, 1),
  (7,  7, 1),
  (8,  6, 2),
  (8,  5, 2),
  (8,  8, 2),
  (9,  2, 4),
  (10, 7, 1);


-- concept hierarchy relationships
INSERT INTO concept_hierarchy (parent_concept_id, child_concept_id, relationship_type) VALUES
  (1, 2, 'is_parent_of'),
  (1, 8, 'is_parent_of'),
  (2, 3, 'is_specialization_of'),
  (4, 5, 'is_prerequisite_of'),
  (6, 7, 'is_prerequisite_of'),
  (1, 3, 'is_parent_of');


-- entity to concept mappings
INSERT INTO entity_concepts (entity_id, concept_id, relevance_score) VALUES
  (3,  1, 0.920),
  (3,  2, 0.930),
  (3,  3, 0.880),
  (4,  1, 0.910),
  (4,  2, 0.900),
  (4,  8, 0.870),
  (1,  6, 0.940),
  (2,  6, 0.920),
  (8,  4, 0.880),
  (9,  5, 0.970),
  (10, 4, 0.850),
  (13, 3, 0.910),
  (14, 8, 0.890),
  (6,  6, 0.890),
  (7,  7, 0.870);


-- concepts extracted from each document
INSERT INTO document_concepts (document_id, concept_id, relevance_score, extracted_by) VALUES
  (1,  1, 0.900, 'system'),
  (1,  2, 0.940, 'system'),
  (1,  8, 0.960, 'system'),

  (2,  6, 0.980, 'system'),
  (2,  7, 0.860, 'system'),

  (3,  4, 0.820, 'system'),
  (3,  5, 0.750, 'manual'),

  (4,  5, 0.990, 'system'),
  (4,  4, 0.800, 'manual'),

  (5,  1, 0.850, 'system'),
  (5,  2, 0.880, 'system'),
  (5,  7, 0.740, 'system'),

  (6,  4, 0.970, 'system'),
  (6,  5, 0.830, 'manual'),

  (7,  6, 0.890, 'system'),

  (8,  3, 0.990, 'system'),
  (8,  2, 0.910, 'system'),
  (8,  5, 0.860, 'ai'),

  (9,  6, 0.920, 'system'),
  (9,  7, 0.880, 'system'),

  (10, 4, 0.640, 'system'),
  (10, 7, 0.720, 'system');


-- vector embeddings for documents and entities
INSERT INTO embeddings (source_type, source_id, model_name, vector, dimensions) VALUES
  ('document', 1,  'text-embedding-ada-002', ARRAY[0.1823, -0.3411,  0.5029,  0.2184, -0.6103,  0.4417, -0.1592,  0.7841], 8),
  ('document', 2,  'text-embedding-ada-002', ARRAY[-0.4293, 0.6812, -0.1034,  0.5551,  0.3382, -0.4920,  0.2271, -0.3148], 8),
  ('document', 3,  'text-embedding-ada-002', ARRAY[0.3341, -0.2218,  0.7129, -0.1093,  0.5522,  0.3803, -0.6714,  0.1029], 8),
  ('document', 4,  'text-embedding-ada-002', ARRAY[-0.5814,  0.4091,  0.2233, -0.7102,  0.1578,  0.5930, -0.2481,  0.3744], 8),
  ('document', 5,  'text-embedding-ada-002', ARRAY[0.2917,  0.5533, -0.3829,  0.4401, -0.2114,  0.6229,  0.1088, -0.5082], 8),
  ('document', 6,  'text-embedding-ada-002', ARRAY[-0.1408,  0.7823, -0.4931,  0.2017,  0.5614, -0.3320,  0.4819, -0.2581], 8),
  ('document', 7,  'text-embedding-ada-002', ARRAY[0.6112, -0.1744,  0.2553,  0.5094, -0.4231,  0.1897,  0.7301, -0.3488], 8),
  ('document', 8,  'text-embedding-ada-002', ARRAY[-0.3729,  0.5014,  0.6318, -0.2847,  0.1193,  0.7041, -0.4512,  0.2231], 8),
  ('document', 9,  'text-embedding-ada-002', ARRAY[0.4838, -0.6201,  0.1529,  0.3814,  0.5440, -0.2038,  0.3792, -0.5113], 8),
  ('document', 10, 'text-embedding-ada-002', ARRAY[-0.2011,  0.3924, -0.5718,  0.6431,  0.2294, -0.7018,  0.1347,  0.4589], 8),

  ('entity',   1,  'text-embedding-ada-002', ARRAY[0.5841, -0.3012,  0.2284,  0.6019, -0.4113,  0.3551, -0.2809,  0.5023], 8),
  ('entity',   3,  'text-embedding-ada-002', ARRAY[-0.2391,  0.6124,  0.4012, -0.5018,  0.3287,  0.4831, -0.6201,  0.1924], 8),
  ('entity',   9,  'text-embedding-ada-002', ARRAY[0.7123, -0.4501,  0.1834,  0.3920, -0.5219,  0.2841,  0.6054, -0.3712], 8);


-- sample query log entries
INSERT INTO query_logs (user_id, query_text, query_type, results_count, execution_ms) VALUES
  (2,  'transformer attention mechanisms BERT',       'keyword_search',  5,  142),
  (5,  'federated learning edge devices privacy',     'semantic_search', 4,  381),
  (7,  'kubernetes deployment best practices',        'keyword_search',  6,  118),
  (8,  'OAuth brute force incident 2025',             'keyword_search',  3,  203),
  (3,  'GDPR data subject access requests',           'semantic_search', 2,  410),
  (4,  'helm rollback failure EKS',                   'keyword_search',  4,  167),
  (1,  'entities linked to Kubernetes',               'graph_traversal', 8,  289),
  (2,  'experts in deep learning',                    'semantic_search', 3,  355),
  (8,  'zero trust NIST controls security',           'keyword_search',  5,  199),
  (5,  'PyTorch migration CI/CD pipeline',            'semantic_search', 4,  402),
  (1,  'graph statistics and entity counts',          'analytics',      12,   87),
  (3,  'GDPR compliance sensitive documents export',  'export',          2,  534);


-- audit log entries
INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address) VALUES
  (1, 'login',         'system',   NULL, 'Admin login at session start',                                '10.0.1.5'),
  (3, 'login',         'system',   NULL, 'Compliance officer login',                                    '10.0.1.22'),
  (7, 'login',         'system',   NULL, 'Consumer user login — Grace Huang',                           '10.0.2.44'),
  (8, 'login',         'system',   NULL, 'Security analyst login — Hiro Yamamoto',                      '10.0.1.31'),

  (3, 'view',          'document',  4,   'Compliance read of restricted GDPR assessment (doc #4)',      '10.0.1.22'),
  (8, 'view',          'document',  3,   'Security analyst read of confidential incident report (doc #3)','10.0.1.31'),
  (3, 'view',          'document',  8,   'Compliance read of confidential federated learning paper',    '10.0.1.22'),

  (7, 'access_denied', 'document',  3,   'Consumer (grace.huang) denied read on confidential doc #3',  '10.0.2.44'),
  (7, 'access_denied', 'document',  4,   'Consumer (grace.huang) denied read on restricted doc #4',    '10.0.2.44'),

  (2, 'create',        'document',  1,   'Ben Okafor uploaded NLP research paper (doc #1)',             '10.0.1.12'),
  (3, 'export',        'document',  4,   'Compliance export of GDPR assessment for external audit',     '10.0.1.22'),

  (1, 'update',        'role',      3,   'Admin updated consumer role permissions — added run_analytics','10.0.1.5');
