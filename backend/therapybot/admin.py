from django.contrib import admin, messages

from therapybot.models import Conversation, KnowledgeArticle, Message, Profile


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
    list_display = ("user", "display_name", "zip_code", "session_format", "terms_accepted_at")
    search_fields = ("user__username", "user__email", "display_name")
    readonly_fields = ("age_confirmed_at", "terms_accepted_at", "updated_at")


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "active", "fetched_at")
    list_filter = ("source", "active")
    search_fields = ("title", "body")
    actions = ["rebuild_index"]

    @admin.action(description="Rebuild the retrieval index (after editing articles)")
    def rebuild_index(self, request, queryset):
        from therapybot.ai import build_index

        build_index()
        self.message_user(request, "Index rebuilt. All server workers pick it up on their next request.", messages.SUCCESS)
