from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Wish(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishes')
    is_active = models.BooleanField(default=True)
    claimed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='claimed_wishes')

    def __str__(self):
        return self.name
    
