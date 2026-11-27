"""The sample contracts every demo shows: four realistic agreements with history, sharing, a
restore, a withdrawn version and a rename (Phase 7 T10; shared with demo workspaces, Phase 9 F1).

Built through the real services, so versions, the activity log and notifications look exactly like
real use. All contract text is original sample text written for this demo, not legal advice.
"""

from sqlalchemy.orm import Session

from app.db.models import Role, User
from app.services import documents as document_service
from app.services import members as member_service
from app.services import versions as version_service

NDA_V1 = """MUTUAL NON-DISCLOSURE AGREEMENT

1. Purpose. The parties wish to explore a possible business relationship and may share
Confidential Information for that purpose only.

2. Confidential Information means any non-public information disclosed by one party to the other,
in any form, that is marked confidential or would reasonably be understood to be confidential.

3. Obligations. The receiving party will protect Confidential Information with at least reasonable
care and will not disclose it to anyone except employees who need to know it.

4. Term. This Agreement lasts for two (2) years from the Effective Date.

5. Governing Law. This Agreement is governed by the laws of the State of New York."""

NDA_V2 = NDA_V1.replace(
    "4. Term. This Agreement lasts for two (2) years from the Effective Date.",
    "4. Term. This Agreement lasts for three (3) years from the Effective Date. Obligations for\n"
    "trade secrets survive for as long as the information remains a trade secret.",
).replace(
    "employees who need to know it.",
    "employees, advisers and contractors who need to know it and are bound by\n"
    "confidentiality obligations at least as protective as these.",
)

LEASE_V1 = """COMMERCIAL LEASE — SUITE 400, 12 HARBOR STREET

1. Premises. Landlord leases to Tenant approximately 2,400 square feet on the fourth floor.

2. Term. Five (5) years, starting on the Commencement Date.

3. Rent. Base rent is $9,600 per month, payable on the first day of each month.

4. Security Deposit. Tenant will pay a deposit equal to two months' rent.

5. Maintenance. Tenant maintains the interior; Landlord maintains the roof, structure and
building systems."""

LEASE_V2 = LEASE_V1.replace(
    "Base rent is $9,600 per month", "Base rent is $9,200 per month, increasing 3% each year"
)
LEASE_V3 = LEASE_V2.replace(
    "equal to two months' rent.", "equal to one month's rent, refundable within 30 days."
)

MSA_V1 = """MASTER SERVICES AGREEMENT

1. Services. Provider will deliver the services described in each signed Statement of Work.

2. Fees. Customer pays the fees in each Statement of Work within thirty (30) days of invoice.

3. Service Levels. Provider will make the platform available 99.5% of each calendar month.

4. Limitation of Liability. Each party's total liability is limited to the fees paid in the
twelve (12) months before the claim.

5. Termination. Either party may terminate for convenience with sixty (60) days' written notice."""

MSA_V2 = MSA_V1.replace("99.5% of each calendar month", "99.9% of each calendar month").replace(
    "thirty (30) days of invoice", "forty-five (45) days of invoice"
)
MSA_V3_REJECTED = MSA_V2.replace(
    "limited to the fees paid in the\ntwelve (12) months",
    "limited to the fees paid in the\nthree (3) months",
)

OFFER_V1 = """EMPLOYMENT AGREEMENT — SENIOR PARALEGAL

1. Position. Employee will work as Senior Paralegal, reporting to the General Counsel.

2. Start Date. Employment begins on the date both parties sign.

3. Compensation. Base salary of $78,000 per year, paid every two weeks.

4. Notice. Either party may end employment with two (2) weeks' written notice."""

OFFER_V2 = OFFER_V1.replace("$78,000 per year", "$82,000 per year").replace(
    "two (2) weeks' written notice", "four (4) weeks' written notice"
)


def populate(db: Session, asha: User, ben: User, chloe: User) -> None:
    """Create the four sample contracts for three accounts, in their roles."""

    def access(user: User, document_id: int) -> document_service.DocumentAccess:
        return document_service.get_document_access(
            db, document_id=document_id, user=user, minimum=Role.VIEWER
        )

    # 1. NDA: Asha owns it, Ben edits, Chloe reviews.
    nda, _ = document_service.create_document(
        db, title="Mutual NDA — Northwind Ltd", content=NDA_V1, user=asha
    )
    member_service.add_member(db, access(asha, nda.id), email=ben.email, role=Role.EDITOR)
    member_service.add_member(db, access(asha, nda.id), email=chloe.email, role=Role.VIEWER)
    version_service.create_version(
        db, nda, content=NDA_V2, user=ben, change_note="Longer term; advisers may receive info"
    )

    # 2. Lease: Ben owns it; a counter-offer, then a deposit change; Asha may edit.
    lease, _ = document_service.create_document(
        db, title="Commercial Lease — 12 Harbor St", content=LEASE_V1, user=ben
    )
    member_service.add_member(db, access(ben, lease.id), email=asha.email, role=Role.VIEWER)
    member_service.change_role(db, access(ben, lease.id), user_id=asha.id, role=Role.EDITOR)
    version_service.create_version(
        db, lease, content=LEASE_V2, user=ben, change_note="Landlord's counter-offer on rent"
    )
    version_service.create_version(
        db, lease, content=LEASE_V3, user=asha, change_note="Deposit reduced to one month"
    )

    # 3. MSA: a bad edit is restored away, and a draft is withdrawn (soft delete).
    msa, _ = document_service.create_document(
        db, title="Master Services Agreement — Contoso", content=MSA_V1, user=asha
    )
    member_service.add_member(db, access(asha, msa.id), email=chloe.email, role=Role.EDITOR)
    version_service.create_version(
        db, msa, content=MSA_V2, user=chloe, change_note="Higher uptime; 45-day payment"
    )
    version_service.create_version(
        db, msa, content=MSA_V3_REJECTED, user=chloe, change_note="Draft: lower liability cap"
    )
    version_service.restore_version(
        db, msa, version_number=2, user=asha, change_note="Liability cap change rejected"
    )
    version_service.delete_version(db, msa, version_number=3, user=asha)

    # 4. Offer letter: Chloe owns it and renames it after negotiation.
    offer, _ = document_service.create_document(
        db, title="Offer — Senior Paralegal", content=OFFER_V1, user=chloe
    )
    member_service.add_member(db, access(chloe, offer.id), email=asha.email, role=Role.VIEWER)
    version_service.create_version(
        db, offer, content=OFFER_V2, user=chloe, change_note="Salary and notice agreed"
    )
    document_service.rename_document(
        db, offer, title="Employment Agreement — Senior Paralegal", actor=chloe
    )
