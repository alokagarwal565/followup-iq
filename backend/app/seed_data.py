"""Fictional demo data: 22 leads, 12 WhatsApp-style chats, 10 Excel-only leads.

All names, companies and numbers are invented. Phones use the synthetic +91 90000 0xxxx range.
Timing is relative (days ago + local time) so the queue always shows a realistic mix of overdue,
due-today and upcoming leads; relative phrases in chats avoid weekday names for the same reason.
"""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid5

_NAMESPACE = UUID("6f1b8d2e-4c3a-4e8b-9a51-7d2f0c9e3b14")


@dataclass(frozen=True)
class SeedMessage:
    sender: Literal["rep", "buyer"]
    days_ago: int
    time: str  # HH:MM in the business timezone
    body: str


@dataclass(frozen=True)
class SeedLead:
    key: str
    name: str
    company: str
    phone: str
    source: str
    rep: str
    created_days_ago: int
    scenario: str
    expected_label: str
    messages: list[SeedMessage] = field(default_factory=list)
    # Only for leads without a chat (the Excel sheet); chat leads derive it from their messages.
    last_contact_days_ago: int | None = None


def seed_lead_id(key: str) -> UUID:
    return uuid5(_NAMESPACE, f"lead:{key}")


def seed_conversation_id(key: str) -> UUID:
    return uuid5(_NAMESPACE, f"conversation:{key}")


def seed_message_id(key: str, index: int) -> UUID:
    return uuid5(_NAMESPACE, f"message:{key}:{index}")


def _phone(n: int) -> str:
    return f"+91 90000 0{1000 + n}"


B: Literal["buyer"] = "buyer"
R: Literal["rep"] = "rep"

SEED_LEADS: list[SeedLead] = [
    SeedLead(
        key="rahul-shree-snacks",
        name="Rahul Mehta",
        company="Shree Snacks Pvt Ltd",
        phone=_phone(1),
        source="IndiaMART",
        rep="Priya Sharma",
        created_days_ago=7,
        scenario="Quote for 2 pouch fillers, ordering this month; promised quote is late",
        expected_label="Hot",
        messages=[
            SeedMessage(
                B,
                6,
                "10:15",
                "Hi, got your number from IndiaMART. Looking for 2 pouch filling machines for namkeen, 200 g and 500 g packs. Can you share details?",
            ),
            SeedMessage(
                R,
                6,
                "10:40",
                "Hi Rahul ji, thanks for reaching out. For namkeen in 200 g and 500 g, a multi-head weigher with a collar-type pouch filler would suit. What output per minute are you targeting?",
            ),
            SeedMessage(
                B,
                5,
                "11:05",
                "Around 40 pouches per minute. We want to order this month, festive demand is high. Please send the quotation for 2 machines.",
            ),
            SeedMessage(
                R,
                5,
                "11:20",
                "Noted, 40 ppm for both sizes. I will send the quotation for 2 machines by day after tomorrow.",
            ),
            SeedMessage(
                B, 2, "18:30", "Any update on the quotation? We need to finalise this week."
            ),
        ],
    ),
    SeedLead(
        key="kavita-masala-magic",
        name="Kavita Iyer",
        company="Masala Magic Foods",
        phone=_phone(2),
        source="Trade show",
        rep="Arjun Mehta",
        created_days_ago=5,
        scenario="Live demo booked for the day after tomorrow; replacing 2 manual lines in 3 weeks",
        expected_label="Hot",
        messages=[
            SeedMessage(
                R,
                4,
                "15:00",
                "Hi Kavita, great meeting you at the PackEx stall. Sharing the brochure for the auger filler we discussed for spice powders.",
            ),
            SeedMessage(
                B,
                4,
                "17:45",
                "Thanks. We are replacing 2 manual lines in the next 3 weeks. Can we see a live demo with our chilli powder?",
            ),
            SeedMessage(
                R,
                1,
                "10:10",
                "Demo is confirmed for the day after tomorrow at 11 am at our Bhiwandi facility. Please bring about 2 kg of your chilli powder.",
            ),
            SeedMessage(B, 1, "12:00", "Confirmed. I will come with our production head."),
        ],
    ),
    SeedLead(
        key="imran-crystal-cosmetics",
        name="Imran Shaikh",
        company="Crystal Cosmetics",
        phone=_phone(3),
        source="Website",
        rep="Neha Kulkarni",
        created_days_ago=11,
        scenario="Price negotiation against a competitor, decision in 3 weeks",
        expected_label="Hot",
        messages=[
            SeedMessage(
                B,
                10,
                "12:30",
                "Need a quote for an automatic sticker labelling machine for 100 ml and 200 ml bottles.",
            ),
            SeedMessage(
                R,
                9,
                "16:00",
                "Sharing the quote for the round-bottle labeller with batch coder. Delivery is 6 weeks from PO.",
            ),
            SeedMessage(
                B,
                1,
                "11:45",
                "We got another offer about 12% lower than yours. We will decide in 3 weeks. Can you revise?",
            ),
            SeedMessage(
                R,
                1,
                "12:10",
                "Understood. Let me check with my manager on the best we can do and get back to you.",
            ),
        ],
    ),
    SeedLead(
        key="deepa-coastal-agro",
        name="Deepa Nair",
        company="Coastal Agro Exports",
        phone=_phone(4),
        source="Referral",
        rep="Rohit Verma",
        created_days_ago=21,
        scenario="Asked about AMC and spares 2 days ago; nobody replied",
        expected_label="Warm",
        messages=[
            SeedMessage(
                R,
                20,
                "11:00",
                "Hi Deepa, Sunil from Coastal Foods referred you. We supply vacuum sealing machines for seafood packing.",
            ),
            SeedMessage(
                B,
                18,
                "14:20",
                "Yes, we are looking at one double-chamber vacuum sealer. What about service support in Kochi?",
            ),
            SeedMessage(
                R,
                18,
                "15:05",
                "We have a service partner in Ernakulam with a 48-hour response time.",
            ),
            SeedMessage(
                B,
                2,
                "10:30",
                "OK. What does your annual maintenance contract cover, and are spares stocked locally?",
            ),
        ],
    ),
    SeedLead(
        key="vikram-joshi-distributors",
        name="Vikram Joshi",
        company="Joshi Distributors",
        phone=_phone(5),
        source="WhatsApp",
        rep="Sana Qureshi",
        created_days_ago=4,
        scenario="Distributor asking about speed and dealer margin, vague volume",
        expected_label="Warm",
        messages=[
            SeedMessage(
                B,
                4,
                "09:50",
                "I am a distributor in Pune for food units. What is the speed of your band sealer and the margin for dealers?",
            ),
            SeedMessage(
                R,
                4,
                "10:30",
                "Hi Vikram, the continuous band sealer runs up to 12 metres per minute. Dealer terms depend on volume. How many units do you expect to place in a year?",
            ),
            SeedMessage(
                B,
                2,
                "17:15",
                "Hard to say, maybe a few. Some clients are asking. Send me the catalogue.",
            ),
            SeedMessage(
                R,
                2,
                "17:40",
                "Sharing the catalogue now. Let me know which clients are interested and I can support with demos.",
            ),
        ],
    ),
    SeedLead(
        key="anita-purepack-dairy",
        name="Anita Desai",
        company="PurePack Dairy",
        phone=_phone(6),
        source="Excel sheet",
        rep="Priya Sharma",
        created_days_ago=9,
        scenario="Waiting on our spec sheet; rep promised to send it the same day (yesterday)",
        expected_label="Warm",
        messages=[
            SeedMessage(
                B,
                8,
                "13:00",
                "We need a cup filling and sealing machine for dahi, 200 g and 400 g cups.",
            ),
            SeedMessage(
                R,
                7,
                "11:15",
                "Hi Anita, our rotary cup filler handles both sizes. Can you confirm the cups per hour you need?",
            ),
            SeedMessage(
                B,
                1,
                "10:05",
                "About 1,800 cups per hour. Please share the technical spec sheet so our plant team can review.",
            ),
            SeedMessage(R, 1, "10:20", "Sure, I will send the spec sheet today."),
        ],
    ),
    SeedLead(
        key="suresh-patil-pickles",
        name="Suresh Patil",
        company="Patil Pickles",
        phone=_phone(7),
        source="IndiaMART",
        rep="Arjun Mehta",
        created_days_ago=31,
        scenario="Budget approved after Diwali; asked to be called in the first week of January",
        expected_label="Warm",
        messages=[
            SeedMessage(B, 30, "12:00", "Need a semi-automatic pickle jar filling machine."),
            SeedMessage(
                R,
                29,
                "11:30",
                "Hi Suresh ji, sharing the quote for the piston filler for 500 g and 1 kg jars.",
            ),
            SeedMessage(R, 6, "10:00", "Hi Suresh ji, any update on the quote?"),
            SeedMessage(
                B,
                5,
                "19:10",
                "Budget gets approved after Diwali. Call me in the first week of January, we will decide then.",
            ),
            SeedMessage(R, 5, "19:25", "Sure, I will call you in the first week of January."),
        ],
    ),
    SeedLead(
        key="farah-noor-herbal",
        name="Farah Khan",
        company="Noor Herbal Care",
        phone=_phone(8),
        source="Website",
        rep="Neha Kulkarni",
        created_days_ago=7,
        scenario="Hinglish chat: wants installation within a month and a quotation",
        expected_label="Hot",
        messages=[
            SeedMessage(
                B,
                6,
                "16:00",
                "Hello, hume herbal oil ke liye bottle filling aur capping machine chahiye. 50 ml aur 100 ml.",
            ),
            SeedMessage(
                R,
                6,
                "16:30",
                "Hi Farah ji, ho jayega. Hamari 4-head liquid filler with capper fit rahegi. Daily kitna production chahiye?",
            ),
            SeedMessage(
                B,
                2,
                "12:45",
                "Roughly 3,000 bottles daily. Diwali ke baad production badhana hai, isliye next month tak machine install ho jani chahiye. Installation me kitna time lagta hai? Quotation bhi bhej dijiye.",
            ),
        ],
    ),
    SeedLead(
        key="manoj-gupta-namkeen",
        name="Manoj Gupta",
        company="Gupta Namkeen",
        phone=_phone(9),
        source="Trade show",
        rep="Rohit Verma",
        created_days_ago=36,
        scenario="Four rep follow-ups unanswered over five weeks",
        expected_label="Cold",
        messages=[
            SeedMessage(
                B,
                35,
                "11:00",
                "Met you at the expo. Send details of the nitrogen flushing pouch packer.",
            ),
            SeedMessage(
                R,
                35,
                "15:00",
                "Hi Manoj ji, sharing the brochure and video of the N2 flush packer.",
            ),
            SeedMessage(
                R,
                28,
                "11:00",
                "Hi Manoj ji, did you get a chance to see the video? Happy to arrange a demo.",
            ),
            SeedMessage(
                R,
                21,
                "11:00",
                "Following up on the N2 flush packer. Let me know if next month is a better time.",
            ),
            SeedMessage(
                R,
                12,
                "11:00",
                "Hi Manoj ji, just checking in once more. Should I keep this open for you?",
            ),
        ],
    ),
    SeedLead(
        key="lata-sunrise-beverages",
        name="Lata Reddy",
        company="Sunrise Beverages",
        phone=_phone(10),
        source="Referral",
        rep="Sana Qureshi",
        created_days_ago=40,
        scenario="Ordered from another supplier",
        expected_label="Cold",
        messages=[
            SeedMessage(
                R,
                25,
                "10:00",
                "Hi Lata, following up on the shrink-sleeve labeller quote for your PET bottles.",
            ),
            SeedMessage(B, 24, "18:00", "We are still comparing options."),
            SeedMessage(R, 9, "10:30", "Hi Lata, any decision on the shrink-sleeve labeller?"),
            SeedMessage(
                B,
                8,
                "13:20",
                "We have ordered from another supplier, thanks. Will keep you in mind for future needs.",
            ),
        ],
    ),
    SeedLead(
        key="ajay-bansal-traders",
        name="Ajay Bansal",
        company="Bansal Traders",
        phone=_phone(11),
        source="WhatsApp",
        rep="Priya Sharma",
        created_days_ago=16,
        scenario="Asked not to be messaged again",
        expected_label="Cold",
        messages=[
            SeedMessage(
                R, 15, "11:00", "Hi Ajay ji, sharing our new range of carton sealing machines."
            ),
            SeedMessage(B, 14, "09:15", "Not needed."),
            SeedMessage(
                R,
                3,
                "11:30",
                "Hi Ajay ji, checking if your carton volumes have changed this season.",
            ),
            SeedMessage(B, 3, "12:05", "Please don't message me again."),
        ],
    ),
    SeedLead(
        key="meera-little-bites",
        name="Meera Pillai",
        company="Little Bites Bakery",
        phone=_phone(12),
        source="Website",
        rep="Arjun Mehta",
        created_days_ago=10,
        # Low volume, but the rep pointed her to a tabletop sealer, so it is a small live
        # opportunity rather than a disqualified lead.
        scenario="Home bakery packing 50 packs a day; rep suggested a tabletop sealer",
        expected_label="Warm",
        messages=[
            SeedMessage(
                B,
                9,
                "20:00",
                "Hi, I run a small home bakery. Is there any small machine to pack cookies? Just exploring.",
            ),
            SeedMessage(R, 9, "20:30", "Hi Meera, how many packs do you make per day?"),
            SeedMessage(B, 7, "09:40", "About 50 packs a day, we pack by hand now."),
            SeedMessage(
                R,
                7,
                "10:15",
                "For 50 packs a day a tabletop heat sealer would be enough. Our automatic machines start at 20 packs per minute, which is more than you need right now.",
            ),
        ],
    ),
    # Excel-sheet leads with no chat history.
    SeedLead(
        key="harish-rao-spices",
        name="Harish Rao",
        company="Rao Spices",
        phone=_phone(13),
        source="Excel sheet",
        rep="Rohit Verma",
        created_days_ago=0,
        scenario="New lead, never contacted",
        expected_label="Warm",
    ),
    SeedLead(
        key="pooja-greenleaf-teas",
        name="Pooja Shetty",
        company="GreenLeaf Teas",
        phone=_phone(14),
        source="Excel sheet",
        rep="Sana Qureshi",
        created_days_ago=6,
        last_contact_days_ago=3,
        scenario="Called once 3 days ago, no chat logged",
        expected_label="Warm",
    ),
    SeedLead(
        key="nikhil-agarwal-foods",
        name="Nikhil Agarwal",
        company="Agarwal Foods",
        phone=_phone(15),
        source="Trade show",
        rep="Priya Sharma",
        created_days_ago=6,
        last_contact_days_ago=3,
        scenario="Met at trade show 3 days ago",
        expected_label="Warm",
    ),
    SeedLead(
        key="sneha-kapoor-organics",
        name="Sneha Kapoor",
        company="Kapoor Organics",
        phone=_phone(16),
        source="Website",
        rep="Neha Kulkarni",
        created_days_ago=2,
        last_contact_days_ago=1,
        scenario="Website enquiry, called yesterday",
        expected_label="Warm",
    ),
    SeedLead(
        key="gaurav-singh-beverages",
        name="Gaurav Singh",
        company="Singh Beverages",
        phone=_phone(17),
        source="Excel sheet",
        rep="Arjun Mehta",
        created_days_ago=20,
        last_contact_days_ago=12,
        scenario="Contacted 12 days ago, follow-up slipped",
        expected_label="Warm",
    ),
    SeedLead(
        key="ritu-malhotra-cosmetics",
        name="Ritu Malhotra",
        company="Malhotra Cosmetics",
        phone=_phone(18),
        source="Excel sheet",
        rep="Rohit Verma",
        created_days_ago=50,
        last_contact_days_ago=33,
        scenario="Stale lead, last contact 33 days ago",
        expected_label="Cold",
    ),
    SeedLead(
        key="amit-jain-pharma",
        name="Amit Jain",
        company="Jain Pharma Packaging",
        phone=_phone(19),
        source="Referral",
        rep="Sana Qureshi",
        created_days_ago=60,
        last_contact_days_ago=45,
        scenario="Stale referral, last contact 45 days ago",
        expected_label="Cold",
    ),
    SeedLead(
        key="kiran-desai-dairy",
        name="Kiran Desai",
        company="Desai Dairy Farms",
        phone=_phone(20),
        source="Excel sheet",
        rep="Priya Sharma",
        created_days_ago=70,
        last_contact_days_ago=60,
        scenario="Stale lead, last contact 60 days ago",
        expected_label="Cold",
    ),
    SeedLead(
        key="sanjay-kulkarni-chemicals",
        name="Sanjay Kulkarni",
        company="Kulkarni Home Care",
        phone=_phone(21),
        source="IndiaMART",
        rep="Neha Kulkarni",
        created_days_ago=40,
        scenario="Imported 40 days ago, never contacted",
        expected_label="Cold",
    ),
    SeedLead(
        key="priyanka-bose-sweets",
        name="Priyanka Bose",
        company="Bose Sweets",
        phone=_phone(22),
        source="IndiaMART",
        rep="Rohit Verma",
        created_days_ago=1,
        scenario="IndiaMART enquiry yesterday, not yet contacted",
        expected_label="Warm",
    ),
]
