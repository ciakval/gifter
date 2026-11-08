from django import forms
from django.db.models import F
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from .models import Event, Wish


class BootstrapFormMixin:
    """Give every widget its Bootstrap class, keeping any classes already set."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput | forms.CheckboxSelectMultiple):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css}".strip()


class EventForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "date", "description"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class EventChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, event):
        if event.date:
            # One translatable string with placeholders, never concatenated pieces.
            return _("%(name)s (%(date)s)") % {
                "name": event.name,
                "date": date_format(event.date),
            }
        return event.name


class WishForm(BootstrapFormMixin, forms.ModelForm):
    events = EventChoiceField(
        queryset=Event.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Share into events"),
    )

    class Meta:
        model = Wish
        fields = ["name", "description", "priority", "events"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        # A wish can only be shared into events the owner belongs to; a forged id fails validation.
        queryset = owner.events.order_by(F("date").asc(nulls_last=True), "name", "pk")
        self.fields["events"].queryset = queryset
        # A new wish starts ticked into every event; an edit keeps the actual shares.
        if not self.is_bound and self.instance.pk is None:
            self.initial["events"] = [event.pk for event in queryset]
