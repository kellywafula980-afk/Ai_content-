from django.db import models
from django.contrib.auth.models import User

class GeneratedContent(models.Model):
    CONTENT_TYPES = [
        ('blog', 'Blog Post'),
        ('social', 'Social Media Caption'),
        ('email', 'Email Newsletter'),
        ('seo', 'SEO Content'),
        ('youtube', 'YouTube Description'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    prompt = models.TextField()
    generated_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    word_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.username} - {self.content_type}"

class UserCredits(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    credits = models.IntegerField(default=5)
    
    def __str__(self):
        return f"{self.user.username} - {self.credits} credits"