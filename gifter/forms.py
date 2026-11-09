from urllib.parse import urlsplit, urlunsplit

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
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


MAX_LINK_LENGTH = 2000


def normalize_links(raw):
    """Parse one-URL-per-line text into a list of normalized http(s) addresses.

    The scheme is checked on the raw line BEFORE any "https://" prefix is added: prefixing first
    would turn "mailto:anna@example.com" into a URL that URLValidator accepts (userinfo + host).
    Every bad line is reported, not just the first.
    """
    validator = URLValidator(schemes=["http", "https"])
    urls = []
    errors = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        error = ValidationError(
            _("“%(value)s” is not a web address starting with http:// or https://."),
            code="invalid_link",
            params={"value": line},
        )
        scheme = urlsplit(line).scheme
        # A "scheme" containing a dot is really a host with a port (alza.cz:8080/x).
        if scheme and "." not in scheme:
            if scheme.lower() not in ("http", "https"):
                errors.append(error)
                continue
            candidate = line
        else:
            candidate = f"https://{line}"
        if len(candidate) > MAX_LINK_LENGTH:
            errors.append(error)
            continue
        try:
            validator(candidate)
            parts = urlsplit(candidate)
        except (ValidationError, ValueError):
            errors.append(error)
            continue
        # Lowercase the scheme and host only; userinfo, path, query and fragment stay as typed.
        userinfo, at, host_port = parts.netloc.rpartition("@")
        netloc = f"{userinfo}{at}{host_port.lower()}"
        url = urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, parts.fragment))
        if url not in urls:
            urls.append(url)
    if errors:
        raise ValidationError(errors)
    return urls


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

    links = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label=_("Links"),
        help_text=_("One web address per line."),
    )

    class Meta:
        model = Wish
        fields = ["name", "description", "priority", "links", "events"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        # A wish can only be shared into events the owner belongs to; a forged id fails validation.
        queryset = owner.events.order_by(F("date").asc(nulls_last=True), "name", "pk")
        self.fields["events"].queryset = queryset
        # A new wish starts ticked into every event; an edit keeps the actual shares.
        if not self.is_bound and self.instance.pk is None:
            self.initial["events"] = [event.pk for event in queryset]

    def clean_links(self):
        return "\n".join(normalize_links(self.cleaned_data["links"]))


class ChipInForm(forms.Form):
    # max_length counts Unicode code points, so 200 x "ž" fits.
    note = forms.CharField(required=False, max_length=200, strip=True, label=_("Note (optional)"))
