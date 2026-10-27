"""Example scenarios for the demo. Static, editable by the user in the UI."""

from __future__ import annotations

from .schemas import Scenario

SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="recruitment-screening",
        title="Recruitment screening",
        category="Employment",
        description=(
            "A mid-sized retailer plans to use an AI system to screen job applications. "
            "It parses CVs and cover letters, scores candidates from 0 to 100 against the job "
            "description and automatically rejects the bottom 60 percent before any recruiter "
            "sees them. The model was trained on ten years of the company's past hiring "
            "decisions. It also analyses video interviews to rate communication style and "
            "enthusiasm. Recruiters only review the shortlist, and candidates are not told that "
            "AI is used. Data is stored by a third-party SaaS vendor in the cloud."
        ),
    ),
    Scenario(
        id="credit-scoring",
        title="Credit scoring",
        category="Financial services",
        description=(
            "A consumer lender wants to replace its scorecard with a gradient-boosted model "
            "that uses transaction history, device data, social media activity and postcode to "
            "decide instantly whether to approve a loan up to 20,000 EUR. Approvals and "
            "declines are fully automated, customers receive a generic decline message, and "
            "analysts review a random sample of 1 percent of decisions each quarter."
        ),
    ),
    Scenario(
        id="medical-diagnosis-assistant",
        title="Medical diagnosis assistant",
        category="Healthcare",
        description=(
            "A hospital network deploys an LLM-based assistant that reads patient records and "
            "radiology reports and proposes a ranked list of likely diagnoses and next tests to "
            "emergency physicians. Physicians see the suggestion in the electronic health record "
            "and can accept it with one click. The assistant calls internal tools to retrieve "
            "lab results and can draft orders. Records include full patient histories."
        ),
    ),
    Scenario(
        id="customer-support",
        title="Customer support assistant",
        category="Customer service",
        description=(
            "An online electronics shop launches a customer support chatbot built on a hosted "
            "LLM. It answers questions about orders, returns and product specifications using "
            "the help-centre articles, looks up order status through an internal API using the "
            "customer's email address, and can issue refunds up to 50 EUR without human review. "
            "Conversations are logged for 12 months to improve the bot."
        ),
    ),
    Scenario(
        id="education-platform",
        title="Education platform",
        category="Education",
        description=(
            "A university uses an AI platform to grade essay assignments and flag suspected "
            "plagiarism or AI-generated writing. The platform assigns a provisional grade, "
            "writes feedback, and reports a probability that a text was machine-written. "
            "Lecturers can override grades, but a flagged probability above 80 percent "
            "automatically opens a misconduct case. The platform also predicts which students "
            "are likely to drop out, using attendance and behavioural data."
        ),
    ),
    Scenario(
        id="smart-city-surveillance",
        title="Smart-city surveillance",
        category="Public sector",
        description=(
            "A city council plans to install 400 cameras with real-time video analytics in "
            "public squares and transport hubs. The system detects crowd density, abandoned "
            "objects and aggressive behaviour, performs facial recognition against a watchlist "
            "supplied by the police, and sends alerts to a control room. Footage is retained "
            "for 90 days. Residents are informed by signs. The vendor is a non-EU company that "
            "hosts the analytics platform remotely."
        ),
    ),
    Scenario(
        id="predictive-maintenance",
        title="Predictive maintenance",
        category="Industry",
        description=(
            "A manufacturer uses machine-learning models on vibration and temperature sensor "
            "data from CNC machines to predict bearing failures and schedule maintenance. "
            "The model produces a failure probability per machine per week, and the "
            "maintenance planner decides which machines to service. No personal data is "
            "processed. The model runs on an on-premises server inside the factory network."
        ),
    ),
)


def get_scenario(scenario_id: str) -> Scenario | None:
    return next((s for s in SCENARIOS if s.id == scenario_id), None)
