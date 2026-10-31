from django.contrib import admin, messages

from django.utils import timezone

from therapybot.models import AuditEvent, CareRelationship, Client, Conversation, KnowledgeArticle, Message, Practice, PracticeMembership, Profile


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "is_crisis", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "therapy_type", "updated_at")
    list_filter = ("therapy_type",)
    search_fields = ("title", "user__username")
    inlines = [MessageInline]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "npi", "npi_status", "display_name", "terms_accepted_at")
    list_filter = ("role", "npi_status")
    search_fields = ("user__username", "user__email", "display_name", "npi")
    actions = ["approve_npi", "reject_npi"]

    @admin.action(description="Approve NPI after manual review")
    def approve_npi(self, request, queryset):
        updated = queryset.filter(role=Profile.Role.THERAPIST).update(
            npi_status=Profile.NpiStatus.VERIFIED, npi_verified_at=timezone.now()
        )
        self.message_user(request, f"Approved {updated} therapist(s).", messages.SUCCESS)

    @admin.action(description="Reject NPI")
    def reject_npi(self, request, queryset):
        updated = queryset.filter(role=Profile.Role.THERAPIST).update(npi_status=Profile.NpiStatus.REJECTED)
        self.message_user(request, f"Rejected {updated} therapist(s).", messages.WARNING)
    readonly_fields = ("age_confirmed_at", "terms_accepted_at", "updated_at")


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "active", "fetched_at")
    list_filter = ("source", "active")
    search_fields = ("title", "body")
    actions = ["rebuild_index"]

    @admin.action(description="Rebuild the retrieval index (after editing articles)")
    def rebuild_index(self, request, queryset):
        from therapybot.rag import build_index

        build_index()
        self.message_user(request, "Index rebuilt. All server workers pick it up on their next request.", messages.SUCCESS)


admin.site.register(Practice)
admin.site.register(PracticeMembership)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("display_name", "practice", "user", "created_at")
    search_fields = ("display_name", "practice__name")


@admin.register(CareRelationship)
class CareRelationshipAdmin(admin.ModelAdmin):
    list_display = ("client", "therapist", "status", "consented_at", "ended_at")
    list_filter = ("status",)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Read-only: the audit log is append-only."""

    list_display = ("created_at", "actor", "action", "outcome", "client", "object_type", "object_id")
    list_filter = ("outcome", "action")
    search_fields = ("action", "actor__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
