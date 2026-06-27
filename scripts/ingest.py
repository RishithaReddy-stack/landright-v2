"""
Qdrant Ingest Script
--------------------
Chunks and embeds the LandRight knowledge base into Qdrant Cloud.

Run from the project root:
    python scripts/ingest.py

Requirements: sentence-transformers, qdrant-client (already in requirements.txt)
"""
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

from backend.core.config import settings

# ── Config ─────────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 500   # characters
CHUNK_OVERLAP = 50
VECTOR_DIM    = 384   # all-MiniLM-L6-v2 output size

# ── Knowledge base ─────────────────────────────────────────────────────────────
DOCUMENTS = [
    {
        "title": "OPT Application Process",
        "content": """
Optional Practical Training (OPT) allows F-1 students to work in the US for up to 12 months in a job related to their major.

Timeline:
- You can apply 90 days before your program end date and no later than 60 days after.
- The OPT application window opens 90 days before your graduation date.
- USCIS processing takes 3-5 months, so apply as early as possible.
- Your EAD (Employment Authorization Document) is your work permit — you cannot start working until you receive it.

Steps to apply:
1. Request an OPT recommendation from your DSO (Designated School Official) in your school's international office.
2. Your DSO will update your SEVIS record and issue a new I-20 with the OPT recommendation.
3. File Form I-765 (Application for Employment Authorization) with USCIS.
4. Include: signed I-20, copy of passport, copy of visa, copy of I-94, passport-style photos, Form I-765, filing fee ($520 as of 2024).
5. Mail to the correct USCIS lockbox address (check uscis.gov for current address).

Your OPT start date can be up to 60 days after your program end date. Choose carefully — once approved, the date cannot be changed.
        """
    },
    {
        "title": "STEM OPT Extension",
        "content": """
If you have a degree in a STEM field (Science, Technology, Engineering, Mathematics), you can apply for a 24-month STEM OPT extension after your initial 12-month OPT.

Eligibility:
- Your degree must be in a STEM-designated field (check the DHS STEM list).
- Your employer must be enrolled in E-Verify.
- You must apply before your current OPT EAD expires.

Timeline:
- Apply up to 90 days before your OPT expires.
- You get a 180-day cap-gap extension while your application is pending.

Steps:
1. Get a job offer from an E-Verify employer.
2. Complete Form I-983 (Training Plan) with your employer.
3. Submit the I-983 to your DSO.
4. DSO issues a new I-20 recommending STEM extension.
5. File Form I-765 again with the new I-20 and supporting documents.

STEM extension gives you a total of 3 years of OPT work authorization.
        """
    },
    {
        "title": "CPT - Curricular Practical Training",
        "content": """
CPT (Curricular Practical Training) allows F-1 students to work off-campus as part of their curriculum while still enrolled.

Key differences from OPT:
- CPT requires enrollment — you must be actively taking classes.
- CPT is authorized by your DSO, not USCIS — no USCIS filing needed.
- CPT can be part-time (under 20 hours/week) or full-time (20+ hours/week).
- If you use 12+ months of full-time CPT, you become ineligible for OPT.

Who qualifies:
- Students who have been enrolled for at least one academic year (with some exceptions for graduate programs).
- The work must be an integral part of your curriculum (internship course, thesis research, etc.).

How to get CPT:
1. Get a job or internship offer.
2. Register for a co-op or internship course at your school.
3. Request CPT authorization from your DSO.
4. DSO issues a new I-20 with CPT authorization — the employer name, dates, and hours are listed on the I-20.
5. Show your I-20 to your employer — that's your authorization, no separate card is issued.

CPT expires when the semester ends. Renew each semester if needed.
        """
    },
    {
        "title": "Social Security Number (SSN) for F-1 Students",
        "content": """
An SSN (Social Security Number) is required for employment and is needed for many financial services in the US.

When you can apply:
- You must have a job offer or be currently employed to apply for an SSN.
- You need either OPT/CPT authorization or an on-campus job offer.
- You must have been in the US for at least 10 days before applying.

Documents needed:
1. Passport
2. F-1 visa
3. I-94 (arrival record — print from i94.cbp.dhs.gov)
4. I-20 with OPT/CPT authorization (or letter from employer for on-campus work)
5. EAD card (if on OPT)
6. Offer letter or proof of employment

Steps:
1. Gather all documents.
2. Visit your local Social Security Administration (SSA) office in person.
3. Complete Form SS-5 (Application for Social Security Card).
4. SSN card arrives by mail in 2-4 weeks.

Without SSN: Many employers can start you with just an SSN application receipt. Some banks also accept an ITIN (Individual Taxpayer Identification Number) instead of SSN.
        """
    },
    {
        "title": "Opening a Bank Account as an International Student",
        "content": """
Opening a US bank account is one of the first things to do after arrival.

What you need:
- Passport
- F-1 visa
- I-20
- I-94 (print from i94.cbp.dhs.gov)
- US address (your dorm or apartment)
- Some banks also accept a student ID

Banks that are international-student friendly:
- Chase: widely available, good for students, requires SSN or ITIN at most branches but some accept I-20.
- Bank of America: similar to Chase, campus branches often easier for students.
- Wells Fargo: similar options.
- Citibank: international-friendly, useful if you have an existing Citi account abroad.
- Online banks (Wise, Revolut, Mercury): do not require SSN, great for early days.

Recommended first steps:
1. Open a Wise or Revolut account online immediately on arrival — no SSN needed, great exchange rates.
2. Once you have your SSN, open a Chase or BoA checking account for a more permanent option.
3. After 6 months, apply for a secured credit card to start building credit history.

Do not keep large amounts of cash. Set up direct deposit with your employer as soon as you start working.
        """
    },
    {
        "title": "Taxes for F-1 Students",
        "content": """
All F-1 students must file taxes every year, even if they had no income.

Key forms:
- Form 8843: Required for ALL F-1 students, even with zero income. It's a statement of exempt individual status.
- Form 1040-NR: Required if you earned US income (wages, stipends, scholarships over tuition).

Residency for tax purposes:
- F-1 students are considered non-resident aliens for tax purposes for the first 5 calendar years in the US.
- Non-residents cannot use TurboTax — use Sprintax or Glacier Tax Prep instead.

Deadlines:
- April 15: Tax filing deadline for income earned in the previous calendar year.
- If you had no income, you still need to file Form 8843 by June 15.

Common mistakes:
- Filing as a resident alien when you're still a non-resident (first 5 years).
- Not reporting scholarship/fellowship income that exceeds tuition.
- Missing the filing deadline (there are penalties and it can affect visa status).

Tax treaties: Some countries have tax treaties with the US that reduce or eliminate taxes on certain income. Check if your home country has a treaty.

Recommended tools: Sprintax (paid), Glacier Tax Prep (usually provided by universities), or your university's international office for free assistance.
        """
    },
    {
        "title": "Health Insurance for International Students",
        "content": """
Health insurance is essential in the US — medical bills without insurance can be catastrophically expensive.

University plans:
- Most universities require international students to have health insurance and offer their own student health plan.
- You're usually automatically enrolled and charged the premium with tuition.
- University plans are often the most convenient option and cover campus health services.

Waiving university insurance:
- If you have comparable coverage elsewhere, you can apply to waive the university plan.
- Waiver deadlines are usually at the start of each semester — don't miss them.

What to look for in a plan:
- Premium (monthly cost)
- Deductible (what you pay before insurance kicks in)
- In-network vs out-of-network coverage
- Mental health coverage
- Prescription drug coverage

Using your insurance:
- Always carry your insurance card.
- Use in-network providers to minimize out-of-pocket costs.
- The campus health center is usually free or low-cost for basic visits.
- For emergencies, go to an ER — you cannot be turned away regardless of insurance.

Open enrollment periods typically align with the academic year. Outside of enrollment, you can only change plans if you have a qualifying life event.
        """
    },
    {
        "title": "Driver's License for International Students",
        "content": """
Getting a US driver's license allows you to drive legally and serves as a valid US ID.

Can you drive with your home country license?
- Yes, for a limited time — typically 1 year from your entry date.
- After that, you need a US state driver's license.
- An International Driving Permit (IDP) from your home country can extend this.

What you need to get a state license:
1. Proof of identity: passport
2. Proof of legal presence: I-20 + F-1 visa + I-94
3. Proof of state residency: utility bill, bank statement, or lease with your name and address
4. Social Security Number or proof of ineligibility (some states issue a license without SSN)
5. Pass the written test (rules of the road) and driving test

Steps:
1. Study the state's driver's handbook (available on the DMV website).
2. Schedule an appointment at your local DMV.
3. Pass the written knowledge test.
4. Schedule and pass the driving skills test (you need a car).
5. Pay the license fee (varies by state, typically $25-50).

Note: Each state has different rules. Some states are more international-student friendly than others (e.g., Texas, California). Check your specific state's DMV website.
        """
    },
    {
        "title": "Pre-Arrival Checklist for F-1 Students",
        "content": """
Things to do before you arrive in the US on an F-1 visa:

Documents to have ready:
- Valid passport (must be valid for at least 6 months beyond your program end date)
- F-1 visa stamp in passport
- Original I-20 signed by your DSO
- SEVIS fee payment receipt (Form I-901)
- University admission letter
- Financial proof (bank statements showing you can support yourself)

Housing:
- Arrange housing before arrival — on-campus dorms or off-campus apartments.
- If off-campus, have the address ready for your I-94 and other forms.

Money:
- Bring some USD cash for immediate expenses (airport, food, transport).
- Set up Wise or Revolut before departure to transfer money at low cost.
- Inform your home bank of your travel so cards aren't blocked.

Electronics:
- US uses 120V/60Hz — bring adapters if needed (most laptops are universal).
- Get an unlocked phone or plan to buy a prepaid SIM on arrival.

Entry to US:
- At the port of entry, you'll go through CBP (Customs and Border Protection).
- Present your passport, visa, I-20, and SEVIS receipt.
- The officer will stamp your passport and you'll get an I-94 record (electronic).
- Check your I-94 at i94.cbp.dhs.gov within a few days to confirm it's correct.
        """
    },
    {
        "title": "Post-Arrival Checklist for F-1 Students",
        "content": """
Things to do in the first 2 weeks after arriving in the US:

Day 1-3:
- Check your I-94 at i94.cbp.dhs.gov — make sure your status shows F-1 and D/S (Duration of Status).
- Print your I-94 and keep it safe.
- Check in with your university's international student office — this is usually required and activates your SEVIS record.
- Get a US SIM card (T-Mobile, Mint Mobile, or campus carrier).

Week 1:
- Open a Wise or Revolut account if you haven't already.
- Get your university student ID.
- Set up your university email and student portal.
- Locate the campus health center and register if needed.
- Find the nearest grocery store, pharmacy, and urgent care.

Week 2:
- Open a US bank account (Chase or BoA campus branch).
- Get your Social Security Number if you have campus employment or OPT/CPT.
- Register your address with the US Postal Service if needed.
- Explore public transit options or get a bike.

Important: Report your address to the international office whenever you move — F-1 regulations require your address on file to be current at all times.
        """
    },
    {
        "title": "F-1 Visa Rules and Maintaining Status",
        "content": """
Understanding your F-1 status is critical — violations can lead to loss of status and deportation.

Key rules:
- Full-time enrollment: You must be enrolled full-time every semester (usually 12 credits for undergrad, 9 for grad). Dropping below full-time requires DSO approval.
- On-campus work: You can work on campus up to 20 hours/week during the semester, full-time during breaks.
- Off-campus work: Only authorized through CPT, OPT, or severe economic hardship — never work off-campus without authorization.
- Travel: You need a valid visa stamp to re-enter the US. Your I-20 must be signed by your DSO within the last 12 months for travel.
- Program extension: If you need more time to complete your degree, ask your DSO for an I-20 extension before your current I-20 expires.
- Grace periods: You have 60 days after your program ends (or OPT ends) to leave the US or change status.

What can get you in trouble:
- Working without authorization
- Dropping below full-time without DSO approval
- Letting your I-20 expire without extension
- Transferring schools without notifying both DSOs
- Staying beyond your grace period

Always communicate with your DSO before making any changes to your enrollment, employment, or travel plans.
        """
    },
    {
        "title": "Getting a SIM Card in the US",
        "content": """
Getting a US phone number is one of the first things to do on arrival — you'll need it for bank accounts, job applications, and everyday life.

Options for new arrivals (no SSN needed):
- T-Mobile Prepaid: Available at T-Mobile stores and Walmart. Good nationwide coverage. Plans from $30/month.
- Mint Mobile: Online or Walmart. Uses T-Mobile network. Very affordable — $15/month for 5GB.
- Google Fi: Great for international travelers, works in 200+ countries. No SSN needed to sign up.
- Visible: Verizon network, $25/month unlimited. Good value.
- Campus carriers: Many universities have partnerships with carriers offering student discounts.

What to bring to get a SIM:
- Passport (some stores ask for ID)
- Cash or international credit card (US credit cards work once you have them)

Tips:
- Get an unlocked phone or buy a cheap prepaid Android to start.
- iMessage and WhatsApp work over WiFi until you get a SIM.
- Port your number later to a postpaid plan once you have an SSN and credit history.
- T-Mobile has the best international calling rates if you need to call home frequently.
        """
    },
    {
        "title": "Building Credit History in the US",
        "content": """
Building US credit history is important for renting apartments, getting car loans, and eventually getting a regular credit card.

Why it matters:
- Landlords check credit scores for apartment applications.
- Without credit history, you may need a larger security deposit.
- Good credit unlocks better interest rates and financial products.

How to start with no credit history:
1. Secured credit card: You deposit $200-500 as collateral and get a card with that limit. Discover It Secured and Capital One Secured are international-student friendly — some don't require SSN.
2. Credit-builder loan: Some credit unions offer small loans specifically to build credit.
3. Become an authorized user: If you have a friend or family member with good US credit, ask to be added to their card.
4. International student credit cards: Some cards (Deserve EDU, Petal) are designed for students with no credit history.

Rules to build credit fast:
- Pay your balance in full every month — never miss a payment.
- Keep utilization below 30% (don't use more than $60 of a $200 limit).
- Don't apply for too many cards at once — each application is a hard inquiry.
- After 6-12 months of good history, upgrade to a regular rewards card.

Check your credit score for free at Credit Karma or through your bank's app.
        """
    },
    {
        "title": "Housing Options for International Students",
        "content": """
Finding housing is one of the biggest challenges for new international students.

On-campus housing:
- Dorms and university apartments are the easiest option for first-year students.
- Usually furnished, utilities included, and within walking distance of classes.
- Apply early — on-campus housing fills up fast.
- More expensive per square foot but eliminates the hassle of signing leases.

Off-campus housing:
- Apartments: Lease agreements are typically 12 months. Landlords may ask for proof of income, credit check, and SSN.
- International students often need a co-signer (a US citizen or permanent resident) or a larger security deposit (2-3 months) due to lack of credit history.
- Roommates: Splitting rent is common. Facebook groups, Roomies.com, and university housing boards are good sources.

What to look for:
- Distance to campus (walkable, bikeable, or bus access)
- Safety of the neighborhood
- Proximity to grocery stores
- Utilities included or separate
- Pet policy if applicable
- Month-to-month vs annual lease

Average costs vary widely by city:
- Small college town: $500-800/month for a room
- Mid-size city: $700-1200/month
- NYC, SF, Boston: $1500-2500+ for a room

Always read your lease carefully before signing. Understand the break lease policy, subletting rules, and what happens if a roommate leaves.
        """
    },
]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    text = text.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def main():
    print(f"Connecting to Qdrant at {settings.qdrant_url}...")
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
        prefer_grpc=False,
    )

    print("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    encoder = SentenceTransformer("all-MiniLM-L6-v2")

    # Create or recreate collection
    existing = [c.name for c in client.get_collections().collections]
    if settings.collection_name in existing:
        print(f"Collection '{settings.collection_name}' already exists — recreating...")
        client.delete_collection(settings.collection_name)

    client.create_collection(
        collection_name=settings.collection_name,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"Created collection '{settings.collection_name}'")

    # Ingest documents
    points = []
    total_chunks = 0

    for doc in DOCUMENTS:
        chunks = chunk_text(doc["content"])
        print(f"  {doc['title']}: {len(chunks)} chunks")
        for chunk in chunks:
            vector = encoder.encode(chunk).tolist()
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "title": doc["title"],
                    "content": chunk,
                }
            ))
            total_chunks += 1

    print(f"\nUploading {total_chunks} chunks to Qdrant...")
    client.upsert(
        collection_name=settings.collection_name,
        points=points,
    )

    print(f"\n✓ Done — {len(DOCUMENTS)} documents, {total_chunks} chunks ingested into '{settings.collection_name}'")


if __name__ == "__main__":
    main()
