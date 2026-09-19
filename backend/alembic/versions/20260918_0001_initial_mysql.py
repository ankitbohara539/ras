"""Initial MySQL civic platform schema.

Revision ID: 20260918_0001
Revises:
"""
from alembic import op

revision = "20260918_0001"
down_revision = None
branch_labels = None
depends_on = None


TABLES = [
    """
    CREATE TABLE roles (
      id INT AUTO_INCREMENT PRIMARY KEY,
      code VARCHAR(24) NOT NULL UNIQUE,
      name VARCHAR(80) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE users (
      id CHAR(36) PRIMARY KEY,
      full_name VARCHAR(120) NOT NULL,
      email VARCHAR(320) NOT NULL,
      email_normalized VARCHAR(320) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      phone VARCHAR(32),
      avatar_url VARCHAR(500),
      preferred_language VARCHAR(10) NOT NULL DEFAULT 'en',
      email_verified_at DATETIME(6),
      status VARCHAR(32) NOT NULL,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      INDEX ix_users_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE user_roles (
      user_id CHAR(36) NOT NULL,
      role_id INT NOT NULL,
      assigned_by CHAR(36),
      assigned_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      PRIMARY KEY (user_id, role_id),
      CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(id),
      CONSTRAINT fk_user_roles_actor FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE refresh_sessions (
      id CHAR(36) PRIMARY KEY,
      user_id CHAR(36) NOT NULL,
      family_id CHAR(36) NOT NULL,
      token_hash CHAR(64) NOT NULL UNIQUE,
      expires_at DATETIME(6) NOT NULL,
      revoked_at DATETIME(6),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      last_used_at DATETIME(6),
      user_agent VARCHAR(500),
      ip_hash CHAR(64),
      replaced_by_id CHAR(36),
      INDEX ix_refresh_user (user_id),
      INDEX ix_refresh_family (family_id),
      INDEX ix_refresh_expires (expires_at),
      CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE email_verification_tokens (
      id CHAR(36) PRIMARY KEY,
      user_id CHAR(36) NOT NULL,
      token_hash CHAR(64) NOT NULL UNIQUE,
      expires_at DATETIME(6) NOT NULL,
      used_at DATETIME(6),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_verify_user (user_id),
      INDEX ix_verify_expires (expires_at),
      CONSTRAINT fk_verify_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE password_reset_tokens (
      id CHAR(36) PRIMARY KEY,
      user_id CHAR(36) NOT NULL,
      token_hash CHAR(64) NOT NULL UNIQUE,
      expires_at DATETIME(6) NOT NULL,
      used_at DATETIME(6),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_reset_user (user_id),
      INDEX ix_reset_expires (expires_at),
      CONSTRAINT fk_reset_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE user_preferences (
      user_id CHAR(36) PRIMARY KEY,
      language VARCHAR(10) NOT NULL DEFAULT 'en',
      text_scale VARCHAR(12) NOT NULL DEFAULT 'normal',
      high_contrast BOOLEAN NOT NULL DEFAULT FALSE,
      reduced_motion BOOLEAN NOT NULL DEFAULT FALSE,
      text_to_speech BOOLEAN NOT NULL DEFAULT FALSE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      CONSTRAINT fk_preferences_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE emergency_contacts (
      id CHAR(36) PRIMARY KEY,
      user_id CHAR(36) NOT NULL,
      name VARCHAR(120) NOT NULL,
      phone VARCHAR(32) NOT NULL,
      relationship VARCHAR(60),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      INDEX ix_contacts_user (user_id),
      CONSTRAINT fk_contacts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE administrative_areas (
      id CHAR(36) PRIMARY KEY,
      name VARCHAR(160) NOT NULL,
      code VARCHAR(40) NOT NULL UNIQUE,
      parent_id CHAR(36),
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      INDEX ix_areas_name (name),
      CONSTRAINT fk_area_parent FOREIGN KEY (parent_id) REFERENCES administrative_areas(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE issue_categories (
      id CHAR(36) PRIMARY KEY,
      code VARCHAR(50) NOT NULL UNIQUE,
      name VARCHAR(100) NOT NULL,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE issues (
      id CHAR(36) PRIMARY KEY,
      reporter_id CHAR(36) NOT NULL,
      category_id CHAR(36) NOT NULL,
      administrative_area_id CHAR(36),
      title VARCHAR(180) NOT NULL,
      description TEXT NOT NULL,
      status VARCHAR(24) NOT NULL,
      severity VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',
      location POINT NOT NULL SRID 4326,
      address_text VARCHAR(500),
      anonymous_public_display BOOLEAN NOT NULL DEFAULT FALSE,
      client_request_id CHAR(36) NOT NULL UNIQUE,
      version INT NOT NULL DEFAULT 1,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      resolved_at DATETIME(6),
      SPATIAL INDEX sx_issues_location (location),
      INDEX ix_issues_reporter (reporter_id),
      INDEX ix_issues_category (category_id),
      INDEX ix_issues_status_created (status, created_at),
      CONSTRAINT fk_issues_reporter FOREIGN KEY (reporter_id) REFERENCES users(id),
      CONSTRAINT fk_issues_category FOREIGN KEY (category_id) REFERENCES issue_categories(id),
      CONSTRAINT fk_issues_area FOREIGN KEY (administrative_area_id) REFERENCES administrative_areas(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE issue_media (
      id CHAR(36) PRIMARY KEY,
      issue_id CHAR(36) NOT NULL,
      storage_key VARCHAR(500) NOT NULL UNIQUE,
      content_type VARCHAR(80) NOT NULL,
      size_bytes INT NOT NULL,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_issue_media_issue (issue_id),
      CONSTRAINT fk_media_issue FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE issue_votes (
      id CHAR(36) PRIMARY KEY,
      issue_id CHAR(36) NOT NULL,
      user_id CHAR(36) NOT NULL,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      UNIQUE KEY uq_issue_vote_user (issue_id, user_id),
      CONSTRAINT fk_vote_issue FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
      CONSTRAINT fk_vote_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE issue_assignments (
      id CHAR(36) PRIMARY KEY,
      issue_id CHAR(36) NOT NULL,
      assigned_to CHAR(36) NOT NULL,
      assigned_by CHAR(36) NOT NULL,
      assigned_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      completed_at DATETIME(6),
      INDEX ix_assignment_issue (issue_id),
      INDEX ix_assignment_assignee (assigned_to),
      CONSTRAINT fk_assignment_issue FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
      CONSTRAINT fk_assignment_to FOREIGN KEY (assigned_to) REFERENCES users(id),
      CONSTRAINT fk_assignment_by FOREIGN KEY (assigned_by) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE issue_status_history (
      id CHAR(36) PRIMARY KEY,
      issue_id CHAR(36) NOT NULL,
      from_status VARCHAR(24),
      to_status VARCHAR(24) NOT NULL,
      changed_by CHAR(36) NOT NULL,
      note VARCHAR(1000),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_issue_history_issue (issue_id),
      CONSTRAINT fk_history_issue FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
      CONSTRAINT fk_history_actor FOREIGN KEY (changed_by) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


TABLES_CONTINUED = [
    """
    CREATE TABLE civic_service_categories (
      id CHAR(36) PRIMARY KEY,
      code VARCHAR(50) NOT NULL UNIQUE,
      name VARCHAR(120) NOT NULL,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE civic_services (
      id CHAR(36) PRIMARY KEY,
      category_id CHAR(36) NOT NULL,
      administrative_area_id CHAR(36),
      name VARCHAR(180) NOT NULL,
      description TEXT,
      phone VARCHAR(32),
      email VARCHAR(320),
      address VARCHAR(500) NOT NULL,
      location POINT NOT NULL SRID 4326,
      opening_hours JSON,
      emergency_service BOOLEAN NOT NULL DEFAULT FALSE,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      SPATIAL INDEX sx_services_location (location),
      INDEX ix_services_name (name),
      INDEX ix_services_category (category_id),
      CONSTRAINT fk_services_category FOREIGN KEY (category_id) REFERENCES civic_service_categories(id),
      CONSTRAINT fk_services_area FOREIGN KEY (administrative_area_id) REFERENCES administrative_areas(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE emergency_sos (
      id CHAR(36) PRIMARY KEY,
      user_id CHAR(36) NOT NULL,
      emergency_type VARCHAR(60) NOT NULL,
      status VARCHAR(24) NOT NULL,
      location POINT NOT NULL SRID 4326,
      address_text VARCHAR(500),
      message VARCHAR(1000),
      assigned_responder_id CHAR(36),
      acknowledged_at DATETIME(6),
      resolved_at DATETIME(6),
      version INT NOT NULL DEFAULT 1,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      SPATIAL INDEX sx_sos_location (location),
      INDEX ix_sos_status_created (status, created_at),
      INDEX ix_sos_user (user_id),
      INDEX ix_sos_responder (assigned_responder_id),
      CONSTRAINT fk_sos_user FOREIGN KEY (user_id) REFERENCES users(id),
      CONSTRAINT fk_sos_responder FOREIGN KEY (assigned_responder_id) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE emergency_sos_status_history (
      id CHAR(36) PRIMARY KEY,
      emergency_id CHAR(36) NOT NULL,
      from_status VARCHAR(24),
      to_status VARCHAR(24) NOT NULL,
      changed_by CHAR(36) NOT NULL,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_sos_history_emergency (emergency_id),
      CONSTRAINT fk_sos_history_emergency FOREIGN KEY (emergency_id) REFERENCES emergency_sos(id) ON DELETE CASCADE,
      CONSTRAINT fk_sos_history_actor FOREIGN KEY (changed_by) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE emergency_alerts (
      id CHAR(36) PRIMARY KEY,
      title VARCHAR(180) NOT NULL,
      message TEXT NOT NULL,
      severity VARCHAR(20) NOT NULL,
      administrative_area_id CHAR(36),
      created_by CHAR(36) NOT NULL,
      starts_at DATETIME(6) NOT NULL,
      expires_at DATETIME(6),
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
      INDEX ix_alerts_active_expiry (active, expires_at),
      CONSTRAINT fk_alert_area FOREIGN KEY (administrative_area_id) REFERENCES administrative_areas(id),
      CONSTRAINT fk_alert_actor FOREIGN KEY (created_by) REFERENCES users(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE notifications (
      id CHAR(36) PRIMARY KEY,
      event_type VARCHAR(80) NOT NULL,
      title VARCHAR(180) NOT NULL,
      body VARCHAR(1000) NOT NULL,
      payload JSON,
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_notifications_event_created (event_type, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE notification_recipients (
      notification_id CHAR(36) NOT NULL,
      user_id CHAR(36) NOT NULL,
      read_at DATETIME(6),
      PRIMARY KEY (notification_id, user_id),
      INDEX ix_notification_recipient_user (user_id, read_at),
      CONSTRAINT fk_recipient_notification FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
      CONSTRAINT fk_recipient_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE audit_logs (
      id CHAR(36) PRIMARY KEY,
      actor_user_id CHAR(36),
      action VARCHAR(100) NOT NULL,
      target_type VARCHAR(80) NOT NULL,
      target_id VARCHAR(80),
      metadata_json JSON,
      request_id CHAR(36),
      created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
      INDEX ix_audit_action_created (action, created_at),
      INDEX ix_audit_actor (actor_user_id),
      CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def upgrade() -> None:
    for statement in [*TABLES, *TABLES_CONTINUED]:
        op.execute(statement)
    op.execute(
        """
        INSERT INTO roles (code, name) VALUES
          ('CITIZEN', 'Citizen'), ('AUTHORITY', 'Municipal Authority'),
          ('RESPONDER', 'Emergency Responder'), ('ADMIN', 'Platform Administrator')
        """
    )
    op.execute(
        """
        INSERT INTO issue_categories (id, code, name) VALUES
          (UUID(), 'POTHOLE', 'Pothole'), (UUID(), 'GARBAGE', 'Garbage'),
          (UUID(), 'WATER_SUPPLY', 'Water supply'), (UUID(), 'DRAINAGE', 'Drainage'),
          (UUID(), 'STREET_LIGHT', 'Street light'), (UUID(), 'ROAD_DAMAGE', 'Road damage'),
          (UUID(), 'PUBLIC_SAFETY', 'Public safety'), (UUID(), 'ACCESSIBILITY', 'Accessibility problem'),
          (UUID(), 'ELECTRICITY', 'Electricity'), (UUID(), 'OTHER', 'Other')
        """
    )
    op.execute(
        """
        INSERT INTO civic_service_categories (id, code, name) VALUES
          (UUID(), 'HOSPITAL', 'Hospital'), (UUID(), 'POLICE', 'Police'),
          (UUID(), 'FIRE', 'Fire service'), (UUID(), 'SHELTER', 'Shelter'),
          (UUID(), 'MUNICIPAL', 'Municipal office')
        """
    )


def downgrade() -> None:
    for table in [
        "audit_logs", "notification_recipients", "notifications", "emergency_alerts",
        "emergency_sos_status_history", "emergency_sos", "civic_services",
        "civic_service_categories", "issue_status_history", "issue_assignments",
        "issue_votes", "issue_media", "issues", "issue_categories",
        "administrative_areas", "emergency_contacts", "user_preferences",
        "password_reset_tokens", "email_verification_tokens", "refresh_sessions",
        "user_roles", "users", "roles",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table}")
