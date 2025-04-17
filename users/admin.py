from django.contrib import admin
from .models import Itinerary, Activity, PackingChecklist

class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0

@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ('destination', 'user', 'start_date', 'end_date', 'budget', 'created_at')
    list_filter = ('start_date', 'end_date', 'created_at')
    search_fields = ('destination', 'user__username', 'user__email')
    date_hierarchy = 'created_at'
    inlines = [ActivityInline]

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('activity', 'itinerary', 'day_number', 'time', 'cost')
    list_filter = ('day_number', 'itinerary__destination')
    search_fields = ('activity', 'description', 'itinerary__destination')

@admin.register(PackingChecklist)
class PackingChecklistAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'itinerary')
    search_fields = ('itinerary__destination',)
