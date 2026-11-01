"""Re-save existing conversations and messages so chat text is encrypted at rest."""

from django.db import migrations


def encrypt_existing(apps, schema_editor):
    Conversation = apps.get_model("therapybot", "Conversation")
    Message = apps.get_model("therapybot", "Message")
    # Reading tolerates legacy plaintext; saving writes ciphertext. update_fields leaves updated_at alone,
    # which matters: it decides which conversations count as "between sessions".
    for conversation in Conversation.objects.all().iterator():
        conversation.save(update_fields=["title", "summary"])
    for message in Message.objects.all().iterator():
        message.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [("therapybot", "0015_encrypt_chats")]

    operations = [migrations.RunPython(encrypt_existing, migrations.RunPython.noop)]
