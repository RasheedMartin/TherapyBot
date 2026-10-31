"""
Generalize SessionNote into ClinicalDocument (keeping every row), add Session, enable pgvector, and add
the Chunk table for vector search. Written by hand so the renames are renames, not drop-and-recreate.
"""

import django.db.models.deletion
import django.utils.timezone
import pgvector.django
from django.conf import settings
from django.db import migrations, models

import therapybot.fields


class Migration(migrations.Migration):
    dependencies = [
        ("therapybot", "0009_roles_practices_clients_audit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        pgvector.django.VectorExtension(),
        # --- SessionNote -> ClinicalDocument, keeping data -------------------------------------------
        migrations.RenameModel("SessionNote", "ClinicalDocument"),
        migrations.RenameField("clinicaldocument", "user", "owner"),
        migrations.AlterField(
            model_name="clinicaldocument",
            name="owner",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name="session_notes", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RenameField("clinicaldocument", "original_text", "text"),
        migrations.AlterField(
            model_name="clinicaldocument",
            name="text",
            field=therapybot.fields.EncryptedTextField(max_length=20000),
        ),
        migrations.AlterField(
            model_name="clinicaldocument",
            name="explanation",
            field=therapybot.fields.EncryptedJSONField(default=dict),
        ),
        # --- Sessions ----------------------------------------------------------------------------------
        migrations.CreateModel(
            name="Session",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("modality", models.CharField(
                    choices=[("cbt", "CBT"), ("dbt", "DBT"), ("act", "ACT"), ("integrative", "Integrative / other")],
                    default="integrative", max_length=12)),
                ("status", models.CharField(
                    choices=[("scheduled", "Scheduled"), ("completed", "Completed"), ("cancelled", "Cancelled")],
                    default="completed", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions",
                                             to="therapybot.client")),
                ("therapist", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions",
                                                to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date", "-created_at"]},
        ),
        # --- New ClinicalDocument fields (existing rows are client uploads) -----------------------------
        migrations.AddField(
            model_name="clinicaldocument",
            name="client",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name="documents", to="therapybot.client"),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="author",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="session",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="documents", to="therapybot.session"),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="doc_type",
            field=models.CharField(
                choices=[("client_upload", "Uploaded by the client"), ("progress_note", "Progress note"),
                         ("transcript", "Session transcript"), ("intake", "Intake"), ("other", "Other")],
                default="client_upload", max_length=20),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="status",
            field=models.CharField(choices=[("draft", "Draft"), ("final", "Final")], default="final", max_length=10),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="signed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="signed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="+", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="amends",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="amendments", to="therapybot.clinicaldocument"),
        ),
        migrations.AddField(
            model_name="clinicaldocument",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="clinicaldocument",
            constraint=models.CheckConstraint(
                condition=models.Q(("client__isnull", False), ("owner__isnull", False), _connector="OR"),
                name="document_belongs_to_someone",
            ),
        ),
        # --- Vector chunks -------------------------------------------------------------------------------
        migrations.CreateModel(
            name="Chunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corpus", models.CharField(
                    choices=[("client_record", "Client Record"), ("clinical_reference", "Clinical Reference")],
                    max_length=20)),
                ("source_key", models.CharField(max_length=120)),
                ("session_date", models.DateField(blank=True, null=True)),
                ("doc_type", models.CharField(blank=True, max_length=20)),
                ("chunk_index", models.PositiveIntegerField()),
                ("text", therapybot.fields.EncryptedTextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("embedding", pgvector.django.VectorField(dimensions=384)),
                ("content_hash", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("article", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                              related_name="chunks", to="therapybot.knowledgearticle")),
                ("client", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                             related_name="+", to="therapybot.client")),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                               related_name="chunks", to="therapybot.clinicaldocument")),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                            related_name="+", to=settings.AUTH_USER_MODEL)),
                ("practice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                               related_name="+", to="therapybot.practice")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                              related_name="+", to="therapybot.session")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["corpus", "client"], name="chunk_corpus_client"),
                    models.Index(fields=["corpus", "owner"], name="chunk_corpus_owner"),
                    models.Index(fields=["source_key"], name="chunk_source"),
                    pgvector.django.HnswIndex(ef_construction=64, fields=["embedding"], m=16,
                                              name="chunk_embedding_hnsw", opclasses=["vector_cosine_ops"]),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("corpus", "clinical_reference"), ("client__isnull", False),
                                           ("owner__isnull", False), _connector="OR"),
                        name="client_record_chunk_has_owner",
                    ),
                ],
            },
        ),
    ]
