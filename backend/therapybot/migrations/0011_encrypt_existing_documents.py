"""Re-save existing documents so their text and explanations are encrypted at rest."""

from django.db import migrations


def encrypt_existing(apps, schema_editor):
    ClinicalDocument = apps.get_model("therapybot", "ClinicalDocument")
    # Reading tolerates legacy plaintext; saving writes ciphertext
    for doc in ClinicalDocument.objects.all().iterator():
        doc.save(update_fields=["text", "explanation"])


class Migration(migrations.Migration):
    dependencies = [("therapybot", "0010_clinical_records_and_vectors")]

    operations = [migrations.RunPython(encrypt_existing, migrations.RunPython.noop)]
