#!/usr/bin/env python3
"""Generate a comprehensive, realistic demo dataset for the TruthCheck detector.

Label 0 = neutral, attributed, report-style text (reliable journalistic patterns)
Label 1 = sensational / absolute / clickbait / conspiracy-style text (misleading patterns)

Includes diverse real-world news domains (space exploration, clinical medicine,
economic reports, university research, climate data, public policy) alongside
common real-world misinformation patterns (miracle cures, sensational clickbait,
conspiracy theories, urgent viral hoaxes, financial scams).
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

RNG = random.Random(42)
OUT = Path(__file__).resolve().parents[1] / "data" / "dataset.csv"

# ==============================================================================
# REAL NEWS PATTERNS (Label 0)
# ==============================================================================

REAL_TOPICS = [
    # Space & Science
    ("NASA", "the Perseverance rover", "Mars exploration", "traces of ancient water-altered minerals in Jezero crater", "planetary science"),
    ("The European Space Agency", "mission specialists", "solar orbital telemetry", "novel measurements of coronal mass ejections", "astrophysics"),
    ("Astronomers at Caltech", "research teams", "deep space observations", "a distant exoplanet with water vapor in its atmosphere", "astronomy"),
    ("Researchers at CERN", "physicists", "particle collision experiments", "refined mass boundaries for heavy neutrino candidates", "particle physics"),
    ("The James Webb Space Telescope team", "lead scientists", "infrared observations", "high-redshift galaxies formed within 400 million years of the Big Bang", "cosmology"),
    ("ISRO", "flight controllers", "lunar sample tracking", "mineralogical maps of the Moon's south pole region", "space exploration"),

    # Medicine & Health
    ("Johns Hopkins Medicine", "clinical researchers", "a Phase 2 clinical trial", "a 35% reduction in recurring cardiovascular events with targeted therapy", "cardiology"),
    ("The World Health Organization", "epidemiologists", "surveillance data across 45 countries", "a steady decline in global measles transmission following targeted vaccination campaigns", "public health"),
    ("Doctors at Mayo Clinic", "oncology specialists", "a multi-center trial with 850 participants", "improved five-year survival rates using personalized immunotherapy protocols", "oncology"),
    ("The National Institutes of Health", "senior investigators", "longitudinal genomic studies", "three previously unmapped genetic markers associated with late-onset Alzheimer's", "genetics"),
    ("Researchers at Oxford University", "clinical pharmacologists", "a randomized controlled trial published in The Lancet", "that a combined antiviral regimen significantly shortened recovery times", "infectious diseases"),
    ("The Food and Drug Administration", "advisory panel members", "a rigorous safety review", "approval for a novel non-opioid pain management treatment", "pharmacology"),
    ("Scientists at Stanford Medicine", "neurologists", "peer-reviewed brain imaging studies", "distinct neural pathway adaptations following cognitive behavioral interventions", "neuroscience"),
    ("The Indian Council of Medical Research", "health authorities", "national serological surveys", "broad population immunity against seasonal influenza strains", "epidemiology"),

    # Economy & Policy
    ("The Reserve Bank", "monetary policy committee members", "quarterly economic indicators", "keeping the benchmark lending rate unchanged at 6.5% amid moderating inflation", "monetary policy"),
    ("The Bureau of Labor Statistics", "economic analysts", "monthly employment data", "the addition of 175,000 nonfarm payroll jobs and an unemployment rate of 3.8%", "labor economics"),
    ("The Ministry of Finance", "treasury officials", "annual revenue audits", "a 14% increase in direct tax collections driven by digital compliance systems", "fiscal policy"),
    ("The European Central Bank", "governing council representatives", "regional financial stability reports", "gradual easing of headline inflation toward the 2% target", "macroeconomics"),
    ("The Ministry of Education", "education board commissioners", "national curriculum assessments", "a new merit scholarship program supporting 50,000 rural university students", "education policy"),
    ("The Election Commission", "senior electoral officers", "a formal press briefing", "the verified schedule and electronic voting security protocols for upcoming assembly elections", "electoral administration"),
    ("The Supreme Court", "a five-judge constitutional bench", "a unanimous written verdict", "reaffirming fundamental digital privacy standards under administrative law", "judicial rulings"),
    ("Municipal transport authorities", "city engineers", "traffic monitoring sensors", "a 22% reduction in peak-hour commute times following metro line phase two opening", "urban infrastructure"),

    # Environment & Technology
    ("The National Oceanic and Atmospheric Administration", "climate scientists", "ocean temperature sensor arrays", "above-average sea surface temperatures across equatorial Pacific zones", "climate science"),
    ("Engineers at MIT", "materials scientists", "laboratory durability testing", "a high-capacity solid-state battery retaining 92% capacity after 1,000 fast-charge cycles", "clean energy technology"),
    ("The Meteorological Department", "senior meteorologists", "radar and satellite forecast models", "timely onset of southwest monsoon rains across coastal agricultural belts", "meteorology"),
    ("The Geological Survey", "field geologists", "seismic monitoring stations", "identifying stable geothermal energy reserves capable of supporting municipal grid power", "geology"),
    ("Cybersecurity researchers at Carnegie Mellon", "network analysts", "an independent security audit", "patched vulnerabilities in open-source encryption libraries used by cloud providers", "cybersecurity"),
    ("Agricultural scientists at ICAR", "crop researchers", "multi-season field trials", "a drought-resilient wheat variety showing 18% higher yield in low-rainfall regions", "agronomy"),
]

REAL_VERBS = [
    "announced", "confirmed", "reported", "concluded", "published findings on",
    "released detailed data on", "documented", "briefed journalists regarding",
    "verified through independent review", "outlined key milestones in",
]

REAL_SOURCES = [
    "according to a report published in a peer-reviewed journal.",
    "according to official records released during a scheduled press conference.",
    "officials confirmed in an official statement on Monday.",
    "analysts noted, citing audited data presented to parliament.",
    "according to documentation verified by an independent review committee.",
    "spokespersons told reporters following a bilateral review meeting.",
    "according to findings published on the institutional repository.",
    "the full dataset has been made accessible on the government portal for public review.",
    "scientists emphasized in an interview with the press.",
    "according to figures confirmed by multiple participating research hospitals.",
]

REAL_FOLLOWUPS = [
    "The findings were replicated across three independent laboratories prior to publication.",
    "The initiative is scheduled for phased rollout across twelve regional hubs over the next fiscal year.",
    "Senior officials noted that regulatory oversight will be maintained throughout the implementation phase.",
    "Experts emphasized that further long-term monitoring will continue over the next two quarters.",
    "The project was funded through competitive academic research grants and cleared ethical review boards.",
    "Independent auditors verified that all standard testing procedures were rigorously followed.",
    "The comprehensive study included longitudinal follow-ups over an eighteen-month evaluation window.",
    "A formal briefing paper has been submitted to relevant regulatory bodies for technical review.",
]

# ==============================================================================
# FAKE / MISLEADING PATTERNS (Label 1)
# ==============================================================================

FAKE_HOOKS = [
    "SHOCKING", "BREAKING", "YOU WON'T BELIEVE THIS", "URGENT ALERT", "EXPOSED",
    "THEY DON'T WANT YOU TO KNOW", "BOMBSHELL REVELATION", "HORRIFIC TRUTH",
    "MINDBLOWING", "DO NOT IGNORE THIS", "MUST SHARE IMMEDIATELY", "VIRAL LEAK",
    "OFFICIAL STORY IS COLLAPSING", "THE MAINSTREAM MEDIA IS SILENT", "WAKE UP SHEEPLE",
]

FAKE_CLAIMS = [
    "drinking raw onion juice with baking soda cures stage 4 cancer in exactly 48 hours 100% guaranteed",
    "secret government satellites are beaming frequencies into household taps to control civilian thought patterns",
    "big pharma executives held a secret meeting to ban a common backyard weed that permanently reverses all diabetes",
    "a leaked military dossier proves the moon landing was staged in a Hollywood basement and world leaders are clones",
    "schools are secretly microchipping all students through mandatory water bottles without parental consent",
    "the central banking cartel just voted to erase all personal savings accounts at midnight tomorrow",
    "doctors were caught putting tracking chips into seasonal cough syrups to monitor your private conversations",
    "a top scientist broke their silence to reveal that gravity is an illusion created by government radio towers",
    "drinking this secret kitchen spice cleanses every disease known to mankind overnight and doctors are furious",
    "leaked documents confirm elite politicians are secretly passing a bill to tax human breathing and sunlight",
    "tap water nationwide has been poisoned with mind-control chemicals starting tonight so forward this to save lives",
    "a famous cardiologist exposed that hospital heart surgeries are a fake scam to generate trillions in profit",
    "secret underground facilities were discovered housing thousands of alien spacecraft ready to harvest human souls",
    "the government announced an emergency law shutting down the entire internet permanently starting this Friday",
    "this one miraculous ancient fruit melts 30 pounds of pure fat in 3 days with zero diet or exercise required",
    "whistleblowers confirm that voting booths secretly switch all ballots using invisible microwave lasers",
    "eating this forbidden leaf makes you completely immune to every virus forever and pharma companies buried the research",
    "bank insiders confirm a hidden federal program giving away $10,000 cash to anyone who clicks and shares this link",
    "scientists revealed that smartphones are absorbing human memories while you sleep to train deep-state robot armies",
    "an emergency broadcast warning urges everyone to stay indoors because toxic space clouds are entering the atmosphere",
]

FAKE_CONSPIRACIES = [
    "The mainstream media refuses to broadcast this because the elites are terrified.",
    "Pharma billionaires have already threatened to assassinate the brave doctor who leaked this.",
    "Corrupt politicians are working overtime to delete this post off every server right now.",
    "The official story is falling apart and insiders are finally blowing the whistle.",
    "Big corporations are desperately suing to ban this truth from reaching the public.",
    "They are hiding the cure so they can keep charging innocent families millions.",
    "Every major government agency is covering this up to protect their billionaire donors.",
    "The global cabal wants you kept in the dark so they can maintain total control.",
]

FAKE_CALLS_TO_ACTION = [
    "SHARE THIS BEFORE IT GETS DELETED!!!",
    "Forward this to everyone in your contact list RIGHT NOW before it is banned!",
    "Do NOT let them silence the truth — repost immediately across every group!",
    "Wake up and share with your family before it's too late! Time is running out!",
    "Click here before the elites take down the server! 100% verified truth!",
    "Don't wait for the fake news media to tell you — share this viral warning everywhere!",
    "Every person must read this right now! Forward to save innocent lives!",
    "Share before Facebook and Google erase every copy of this shocking footage!",
]


def generate_real_sample() -> str:
    org, people, context, finding, field = RNG.choice(REAL_TOPICS)
    verb = RNG.choice(REAL_VERBS)
    source = RNG.choice(REAL_SOURCES)
    followup = RNG.choice(REAL_FOLLOWUPS)

    patterns = [
        f"{org} has {verb} {finding}, {source} {followup}",
        f"According to {people} at {org}, recent {context} revealed {finding}. {followup} Details were {source}",
        f"A new study in {field} led by {org} {verb} {finding}. {followup}",
        f"In a formal assessment of {context}, {people} from {org} {verb} {finding}. {source}",
        f"{org} announced that {context} produced significant progress, confirming {finding}. {followup}",
    ]
    return RNG.choice(patterns)


def generate_fake_sample() -> str:
    hook = RNG.choice(FAKE_HOOKS)
    claim = RNG.choice(FAKE_CLAIMS)
    conspiracy = RNG.choice(FAKE_CONSPIRACIES)
    cta = RNG.choice(FAKE_CALLS_TO_ACTION)

    patterns = [
        f"{hook}!!! {claim.capitalize()}! {conspiracy} {cta}",
        f"{hook}: Doctors and scientists are STUNNED — {claim}! {conspiracy} {cta}",
        f"They don't want you to know this: {claim}. {conspiracy} PLEASE {cta}",
        f"URGENT WARNING: {claim.capitalize()} — {conspiracy} {cta}",
        f"{hook}! Leaked evidence proves {claim}. {conspiracy} {cta}",
    ]
    return RNG.choice(patterns)


def main() -> None:
    rows: list[tuple[str, int]] = []

    # 600 realistic news reports
    for _ in range(600):
        rows.append((generate_real_sample(), 0))

    # 600 realistic misleading/clickbait samples
    for _ in range(600):
        rows.append((generate_fake_sample(), 1))

    RNG.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["text", "label"])
        writer.writerows(rows)

    print(f"Successfully generated {len(rows)} diverse rows to {OUT}")


if __name__ == "__main__":
    main()
