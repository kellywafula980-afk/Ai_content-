from django import forms

class ContentGenerationForm(forms.Form):
    CONTENT_TYPES = [
        ('blog', '📝 Blog Post'),
        ('social', '📱 Social Media Captions'),
        ('email', '📧 Email Newsletter'),
        ('seo', '🔍 SEO Meta Description'),
        ('youtube', '🎬 YouTube Description'),
    ]
    
    content_type = forms.ChoiceField(
        choices=CONTENT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    topic = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., "10 Tips for Remote Work"'
        })
    )
    tone = forms.ChoiceField(
        choices=[
            ('professional', '💼 Professional'),
            ('casual', '😊 Casual'),
            ('funny', '😂 Funny'),
            ('inspirational', '🌟 Inspirational'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    extra_details = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Add any extra details or keywords...',
            'rows': 3
        })
    )