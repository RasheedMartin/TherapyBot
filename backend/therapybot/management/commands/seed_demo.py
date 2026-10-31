"""
Create a demo practice with a therapist and synthetic clients. Everything here is invented: no real people.

    python manage.py seed_demo            # local development only (DEBUG=true)
    python manage.py seed_demo --reset    # delete the demo data first
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from therapybot.clinical.instruments import INSTRUMENTS
from therapybot.models import (
    CareRelationship,
    Client,
    ClinicalDocument,
    Conversation,
    Plan,
    Practice,
    PracticeMembership,
    Profile,
    Screening,
    Session,
)

PASSWORD = "demo-Therapy-2026"
PRACTICE = "Demo Practice (synthetic data)"

CLIENTS = [
    {
        "username": "demo_jordan", "name": "Jordan Ellis", "modality": "cbt",
        "notes": [
            "Intake. Client is a 29-year-old project manager presenting with work-related anxiety for ~6 months: "
            "racing thoughts before meetings, difficulty falling asleep (5-6 hours/night), avoids speaking up. "
            "GAD-7 = 14 (moderate). Denies SI/HI. Goals: feel calmer at work, sleep 7 hours. Plan: weekly CBT.",
            "Session 2. Psychoeducation on the CBT model. Identified catastrophizing ('If I make one mistake I'll be "
            "fired') and mind reading. Introduced a thought record; client completed one in session. "
            "HW: one thought record per day.",
            "Session 3. Client completed 4 of 7 thought records. Noticed anxiety peaks Sunday evenings. Practiced "
            "paced breathing (4-6). Sleep still ~5.5 hours due to rumination. Plan: add worry time at 6pm; review "
            "stimulus control for sleep next session.",
            "Session 4. Worry time helped on 3 evenings. Client spoke up once in a team meeting and reported "
            "anxiety 6/10 instead of the expected 9/10. Sleep ~6 hours. Plan: graded exposure (speak up in 2 "
            "meetings this week); begin stimulus control.",
        ],
        "homework": [("Thought record", "daily"), ("Worry time at 6pm", "daily")],
        "screenings": [("gad7", 0, 14), ("gad7", 2, 12), ("gad7", 3, 9)],  # (instrument, session index, total)
        # A between-session companion conversation the client shares with the therapist (days ago, messages)
        "chats": [
            ("Speaking up at standup", 3, [
                ("user", "I said I'd speak first at Monday standup and I chickened out again."),
                ("assistant", "That's frustrating, especially after it went better last week. What happened right before?"),
                ("user", "My heart was pounding and I kept thinking everyone would notice my voice shaking."),
                ("assistant", "That sounds like the 'everyone will notice' thought you've been working on. "
                              "Could a thought record help sort out what actually happened?"),
                ("user", "Maybe. I did one after and rated it 7 out of 10 before, 4 after. I'll try again Wednesday."),
            ]),
            ("Can't sleep", 1, [
                ("user", "Up at 3am again thinking about emails."),
                ("assistant", "That's a rough hour to be awake with your thoughts. What have you tried tonight?"),
                ("user", "I got out of bed like my therapist said and read for a bit. Went back to sleep around 4."),
            ]),
        ],
    },
    {
        "username": "demo_priya", "name": "Priya Raman", "modality": "dbt",
        "notes": [
            "Intake. Client is a 34-year-old nurse presenting with intense mood shifts after conflict with her "
            "partner, urges to send angry texts, and feeling 'out of control'. PHQ-9 = 11. Denies current SI; "
            "history of passive SI two years ago, no attempts. Safety plan reviewed. Plan: DBT skills, weekly.",
            "Session 2. Taught STOP skill and TIPP (cold water, paced breathing). Client identified Sunday-night "
            "arguments as the main trigger. HW: diary card daily, use STOP before replying to texts.",
            "Session 3. Diary card completed 5 of 7 days. Used STOP twice; once still sent a text she regretted. "
            "Introduced DEAR MAN for asking her partner for calmer conversations. Plan: role-play DEAR MAN.",
        ],
        "homework": [("Diary card", "daily")],
        "screenings": [("phq9", 0, 11), ("phq9", 2, 8)],
    },
    {
        "username": "demo_marcus", "name": "Marcus Bell", "modality": "act",
        "notes": [
            "Intake. Client is a 52-year-old recently retired teacher presenting with low mood and loss of purpose "
            "since retirement 8 months ago. Withdrawn from friends, sleeping 10 hours. PHQ-9 = 13. Denies SI. "
            "Values exploration planned. Plan: ACT, weekly.",
            "Session 2. Values card sort: connection, learning, contributing. Discussed 'waiting to feel motivated' "
            "as avoidance. Committed action: call one former colleague this week; walk 3x/week.",
        ],
        "homework": [("Walk 20 minutes", "weekdays")],
        "screenings": [("phq9", 0, 13), ("phq9", 1, 11)],
    },
]


class Command(BaseCommand):
    help = "Create a demo practice, therapist and synthetic clients (local development only)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first")
        parser.add_argument("--force", action="store_true", help="Allow running with DEBUG off (never on real data)")

    def handle(self, *args, reset=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("seed_demo only runs with DEBUG=true (pass --force to override on a demo deployment)")
        with transaction.atomic():
            if reset:
                Practice.objects.filter(name=PRACTICE).delete()
                Session.objects.filter(therapist__username="demo_therapist").delete()
                User.objects.filter(username__startswith="demo_").delete()
            if Practice.objects.filter(name=PRACTICE).exists():
                raise CommandError("Demo data already exists; use --reset to recreate it")
            self._seed()
        self.stdout.write(self.style.SUCCESS(
            f"Demo practice created. Therapist: demo_therapist / {PASSWORD}. "
            f"Clients: {', '.join(c['username'] for c in CLIENTS)} (same password)."
        ))

    def _user(self, username, name, role="client"):
        first, last = name.split(" ", 1)
        user = User.objects.create_user(username=username, email=f"{username}@example.com", password=PASSWORD,
                                        first_name=first, last_name=last)
        now = timezone.now()
        Profile.objects.create(
            user=user, role=role, display_name=first, email_verified_at=now, age_confirmed_at=now,
            terms_accepted_at=now,
            **({"npi": "0000000000", "npi_status": "verified", "npi_verified_at": now,
                "npi_details": {"credential": "LCSW", "registry_name": name, "taxonomy": "Demo"}}
               if role == "therapist" else {}),
        )
        return user

    def _seed(self):
        practice = Practice.objects.create(name=PRACTICE)
        therapist = self._user("demo_therapist", "Avery Morgan", role="therapist")
        PracticeMembership.objects.create(practice=practice, user=therapist, role="owner")
        today = timezone.localdate()
        for spec in CLIENTS:
            user = self._user(spec["username"], spec["name"])
            client = Client.objects.create(practice=practice, display_name=spec["name"], email=user.email,
                                           user=user, created_by=therapist)
            CareRelationship.objects.create(client=client, therapist=therapist, status="active",
                                            consented_at=timezone.now())
            count = len(spec["notes"])
            session_dates = [today - timedelta(days=7 * (count - i)) for i in range(count)]
            for instrument_key, session_index, total in spec["screenings"]:
                instrument = INSTRUMENTS[instrument_key]
                responses = [min(3, max(0, total - 3 * i)) for i in range(len(instrument.items))]
                if instrument.risk_item is not None and responses[instrument.risk_item]:
                    # keep the safety item at 0 in demo data; move its points to the first item with room
                    spare = responses[instrument.risk_item]
                    responses[instrument.risk_item] = 0
                    for i in range(len(responses)):
                        room = min(3 - responses[i], spare) if i != instrument.risk_item else 0
                        responses[i] += room
                        spare -= room
                Screening.objects.create(client=client, instrument=instrument_key, responses=responses,
                                         total=sum(responses), severity=instrument.score(responses)[1],
                                         administered_on=session_dates[session_index], source="clinician",
                                         entered_by=therapist)
            for i, text in enumerate(spec["notes"]):
                date = session_dates[i]
                session = Session.objects.create(client=client, therapist=therapist, date=date, modality=spec["modality"])
                ClinicalDocument.objects.create(
                    client=client, author=therapist, session=session, session_date=date, doc_type="progress_note",
                    status="final", signed_at=timezone.now(), signed_by=therapist,
                    title=f"Progress note {date:%b %d}", text=text,
                )
            Session.objects.create(client=client, therapist=therapist, date=today + timedelta(days=2),
                                   modality=spec["modality"], status="scheduled")
            plan = Plan.objects.create(user=user, client=client, assigned_by=therapist, title="Homework")
            for step_title, frequency in spec["homework"]:
                step = plan.steps.create(title=step_title, frequency=frequency)
                for days_ago in (1, 2, 4, 6):  # some check-ins over the last week
                    if step.is_due_on(today - timedelta(days=days_ago)):
                        step.check_ins.create(date=today - timedelta(days=days_ago))
            for title, days_ago, messages in spec.get("chats", []):
                convo = Conversation.objects.create(user=user, title=title, therapy_type="Anxiety Support")
                for role, content in messages:
                    convo.messages.create(role=role, content=content)
                Conversation.objects.filter(pk=convo.pk).update(updated_at=timezone.now() - timedelta(days=days_ago))
