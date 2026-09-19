"""Seed Kathmandu Metropolitan City and its 32 wards.

Revision ID: 20260919_0003
Revises: 20260918_0002
"""

from alembic import op

revision = "20260919_0003"
down_revision = "20260918_0002"
branch_labels = None
depends_on = None


WARDS = (
    (1, "Naxal", "नक्साल"),
    (2, "Lazimpat", "लाजिम्पाट"),
    (3, "Maharajgunj", "महाराजगञ्ज"),
    (4, "Baluwatar", "बालुवाटार"),
    (5, "Hadigaun", "हाँडीगाउँ"),
    (6, "Boudha", "बौद्ध"),
    (7, "Mitra Park", "मित्रपार्क"),
    (8, "Jaya Bageshwori", "जयबागेश्वरी"),
    (9, "Gaushala", "गौशाला"),
    (10, "Baneshwor", "बानेश्वर"),
    (11, "Bag Durbar", "बागदरबार"),
    (12, "Teku", "टेकु"),
    (13, "Kalimati", "कालिमाटी"),
    (14, "Kalanki", "कलंकी"),
    (15, "Dallu", "डल्लु"),
    (16, "Balaju", "बालाजु"),
    (17, "Chhetrapati", "क्षेत्रपाटी"),
    (18, "Naradevi", "नरदेवी"),
    (19, "Damaitol", "दमाइटोल"),
    (20, "Bhimsensthan", "भीमसेनस्थान"),
    (21, "Jyabahal", "ज्याबहाल"),
    (22, "Tewahal", "टेवहाल"),
    (23, "Ombahal", "ओमबहाल"),
    (24, "Makhan", "मखन"),
    (25, "Masangalli", "मासंगली"),
    (26, "Lainchaur", "लैनचौर"),
    (27, "Mahaboudha", "महाबौद्ध"),
    (28, "Old Bus Park", "पुरानो बसपार्क"),
    (29, "Anamnagar", "अनामनगर"),
    (30, "Gyaneshwor", "ज्ञानेश्वर"),
    (31, "Shantinagar", "शान्तिनगर"),
    (32, "Koteshwor", "कोटेश्वर"),
)


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO administrative_areas (id, name, code, parent_id, active)
        VALUES ('00000000-0000-4000-8000-000000000000',
                'Kathmandu Metropolitan City / काठमाडौं महानगरपालिका', 'KMC', NULL, TRUE)
        ON DUPLICATE KEY UPDATE
          name = 'Kathmandu Metropolitan City / काठमाडौं महानगरपालिका', active = TRUE
        """
    )
    for number, english, nepali in WARDS:
        area_id = f"00000000-0000-4000-8000-{number:012d}"
        code = f"KMC-WARD-{number:02d}"
        name = f"Ward {number:02d} · {english} / वडा {number} · {nepali}"
        op.execute(
            f"""
            INSERT INTO administrative_areas (id, name, code, parent_id, active)
            VALUES ('{area_id}', '{name}', '{code}',
                    (SELECT city.id FROM (SELECT id FROM administrative_areas WHERE code = 'KMC') city),
                    TRUE)
            ON DUPLICATE KEY UPDATE name = '{name}', active = TRUE
            """
        )


def downgrade() -> None:
    op.execute("DELETE FROM administrative_areas WHERE code LIKE 'KMC-WARD-%'")
    op.execute("DELETE FROM administrative_areas WHERE code = 'KMC'")
