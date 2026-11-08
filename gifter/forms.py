from django import forms

from .models import Event


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
