"""Short list of regulatory concepts for the Governance agent.

Static text, nothing is fetched at runtime. It is a hint for the model, not a legal
source, and entries are worded as concepts that may be relevant.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    name: str
    summary: str


AI_ACT_TIERS: tuple[Concept, ...] = (
    Concept(
        "Potential prohibited practices (AI Act, Article 5 concepts)",
        "Practices the AI Act treats as unacceptable, for example manipulative or "
        "exploitative techniques, social scoring, certain biometric categorisation, "
        "untargeted facial image scraping, emotion inference in workplaces or "
        "education, and certain real-time remote biometric identification in public "
        "spaces for law enforcement. Scope and exceptions are narrow and need legal review.",
    ),
    Concept(
        "Potential high-risk use cases (AI Act, Annex III areas)",
        "Use areas listed as potentially high-risk: biometrics, critical infrastructure, "
        "education and vocational training, employment and worker management, access to "
        "essential private and public services (including credit scoring and benefits), "
        "law enforcement, migration and border control, administration of justice and "
        "democratic processes. Safety components of regulated products can also be in scope.",
    ),
    Concept(
        "High-risk system obligations (concepts)",
        "Risk management system, data and data governance, technical documentation, "
        "record-keeping and logging, transparency to deployers, human oversight, "
        "accuracy, robustness and cybersecurity, quality management, and conformity "
        "assessment before placing on the market.",
    ),
    Concept(
        "Transparency obligations (concepts)",
        "People should be informed when interacting with an AI system, when content is "
        "AI-generated or manipulated, or when emotion recognition or biometric "
        "categorisation is applied. Typical for chatbots and synthetic content.",
    ),
    Concept(
        "General-purpose AI models (concepts)",
        "Providers of general-purpose AI models have documentation and transparency duties. "
        "A deployer building on a third-party model should check what the provider supplies.",
    ),
    Concept(
        "Minimal risk",
        "Most AI uses with no listed high-risk purpose and no special transparency need; "
        "voluntary codes of conduct and good practice are encouraged.",
    ),
)

GDPR_CONCEPTS: tuple[Concept, ...] = (
    Concept(
        "Lawful basis and purpose limitation (GDPR Art. 5-6)",
        "Processing personal data needs a lawful basis and a specified, legitimate purpose.",
    ),
    Concept(
        "Special category data (GDPR Art. 9)",
        "Health, biometric data used for identification, ethnicity, political opinions, "
        "religion, trade union membership, sexual orientation and similar need additional "
        "conditions.",
    ),
    Concept(
        "Automated decision-making (GDPR Art. 22)",
        "Decisions based solely on automated processing with legal or similarly significant "
        "effects are restricted; safeguards include human intervention and the right to contest.",
    ),
    Concept(
        "DPIA (GDPR Art. 35)",
        "A data protection impact assessment is generally expected for high-risk processing "
        "such as systematic monitoring, large-scale special category data or profiling.",
    ),
    Concept(
        "Data subject rights, minimisation, retention, security",
        "Transparency, access, rectification, erasure, data minimisation, storage limitation, "
        "integrity and confidentiality (Art. 5, 12-22, 32).",
    ),
)

OTHER_FRAMEWORKS: tuple[Concept, ...] = (
    Concept(
        "Product safety and sector rules",
        "Medical devices, machinery, financial services and "
        "similar sectors can add their own conformity and supervisory requirements.",
    ),
    Concept(
        "NIS2 / cybersecurity duties",
        "Operators in covered sectors may have cybersecurity "
        "risk-management and incident-reporting duties.",
    ),
    Concept(
        "Consumer, employment and non-discrimination law",
        "National and EU rules on "
        "equal treatment, worker consultation and consumer information may be relevant.",
    ),
    Concept(
        "Voluntary frameworks",
        "ISO/IEC 42001 (AI management system), NIST AI RMF and "
        "ALTAI-style self-assessment lists can structure internal governance.",
    ),
)


def knowledge_brief() -> str:
    """Render the module as compact prompt context."""
    lines: list[str] = ["EU AI Act concepts (hypotheses only):"]
    lines += [f"- {c.name}: {c.summary}" for c in AI_ACT_TIERS]
    lines.append("GDPR concepts:")
    lines += [f"- {c.name}: {c.summary}" for c in GDPR_CONCEPTS]
    lines.append("Other frameworks that may be relevant:")
    lines += [f"- {c.name}: {c.summary}" for c in OTHER_FRAMEWORKS]
    return "\n".join(lines)
