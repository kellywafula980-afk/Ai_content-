from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.conf import settings
from .models import GeneratedContent, UserCredits
from .forms import ContentGenerationForm
import requests
import stripe

GROQ_API_KEY = settings.GROQ_API_KEY
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Set Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

def generate_with_groq(prompt, content_type):
    system_prompts = {
        'blog': """You are a professional blog writer. Write a detailed blog post with:
- Catchy title
- Introduction
- 3-5 main points with subheadings
- Conclusion
- Word count: 500-800 words""",
        
        'social': """You are a social media expert. Write 5 engaging social media captions with different styles and relevant hashtags.""",
        
        'email': """You are an email marketing expert. Write a professional email newsletter with:
- Subject line
- Greeting
- Main content
- Call to action
- Sign-off""",
        
        'seo': """You are an SEO expert. Generate:
1. SEO Title Tag (50-60 characters)
2. Meta Description (150-160 characters)
3. 5-7 SEO Keywords
4. H1 and H2 headings""",
        
        'youtube': """You are a YouTube expert. Create:
1. Video Title
2. Description (200-300 words)
3. 15-20 Tags
4. Call to Action"""
    }
    
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'llama-3.3-70b-versatile',
        'messages': [
            {'role': 'system', 'content': system_prompts.get(content_type, 'You are a helpful assistant.')},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7,
        'max_tokens': 2000
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

def index(request):
    return render(request, 'studio/index.html')

@login_required
def dashboard(request):
    credits, created = UserCredits.objects.get_or_create(user=request.user)
    contents = GeneratedContent.objects.filter(user=request.user).order_by('-created_at')[:10]
    
    return render(request, 'studio/dashboard.html', {
        'credits': credits.credits,
        'contents': contents
    })

@login_required
def generate(request):
    if request.method == 'POST':
        form = ContentGenerationForm(request.POST)
        if form.is_valid():
            credits, created = UserCredits.objects.get_or_create(user=request.user)
            if credits.credits <= 0:
                messages.error(request, 'No credits left! Buy more.')
                return redirect('buy_credits')
            
            content_type = form.cleaned_data['content_type']
            topic = form.cleaned_data['topic']
            tone = form.cleaned_data['tone']
            extra = form.cleaned_data.get('extra_details', '')
            
            prompt = f"Write a {tone} {content_type} about: {topic}. {extra}"
            
            result = generate_with_groq(prompt, content_type)
            
            if result and 'choices' in result and len(result['choices']) > 0:
                generated_text = result['choices'][0]['message']['content']
                
                content = GeneratedContent.objects.create(
                    user=request.user,
                    content_type=content_type,
                    prompt=prompt,
                    generated_text=generated_text,
                    word_count=len(generated_text.split())
                )
                
                credits.credits -= 1
                credits.save()
                
                messages.success(request, '✅ Content generated successfully!')
                
                return render(request, 'studio/result.html', {
                    'content': content,
                    'generated_text': generated_text
                })
            else:
                error_msg = "Unknown error"
                if result and 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown error')
                messages.error(request, f'Error: {error_msg}')
    else:
        form = ContentGenerationForm()
    
    return render(request, 'studio/generate.html', {'form': form})

@login_required
def buy_credits(request):
    return render(request, 'studio/buy_credits.html', {
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })

@login_required
def create_checkout_session(request):
    if request.method == 'POST':
        plan = request.POST.get('plan')
        
        plans = {
            'starter': {'price': 999, 'credits': 20, 'name': 'Starter Pack'},
            'pro': {'price': 1999, 'credits': 50, 'name': 'Pro Pack'},
            'business': {'price': 4999, 'credits': 200, 'name': 'Business Pack'},
        }
        
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'{plans[plan]["name"]} - {plans[plan]["credits"]} Credits',
                        },
                        'unit_amount': plans[plan]['price'],
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri('/dashboard/'),
                cancel_url=request.build_absolute_uri('/buy-credits/'),
                metadata={
                    'user_id': request.user.id,
                    'credits': plans[plan]['credits'],
                    'plan': plan
                }
            )
            return redirect(checkout_session.url, 303)
        except Exception as e:
            messages.error(request, f'Payment error: {str(e)}')
            return redirect('buy_credits')
    
    return redirect('buy_credits')

# Webhook to add credits after successful payment
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, 'whsec_your_webhook_secret_here'
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata'].get('user_id')
        credits = session['metadata'].get('credits')
        
        if user_id and credits:
            try:
                user = User.objects.get(id=user_id)
                user_credits, created = UserCredits.objects.get_or_create(user=user)
                user_credits.credits += int(credits)
                user_credits.save()
                print(f"✅ Added {credits} credits to user {user.username}")
            except Exception as e:
                print(f"❌ Error adding credits: {e}")
    
    return HttpResponse(status=200)

@login_required
def content_detail(request, content_id):
    content = GeneratedContent.objects.get(id=content_id, user=request.user)
    return render(request, 'studio/content_detail.html', {'content': content})

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'studio/register.html')
        
        user = User.objects.create_user(username, email, password)
        UserCredits.objects.create(user=user, credits=5)
        login(request, user)
        messages.success(request, 'Welcome! You have 5 free credits.')
        return redirect('dashboard')
    
    return render(request, 'studio/register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'studio/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('index')


def create_checkout_session(request):
    if request.method == 'POST':
        plan = request.POST.get('plan')
        
        plans = {
            'starter': {'price': 999, 'credits': 20, 'name': 'Starter Pack'},
            'pro': {'price': 1999, 'credits': 50, 'name': 'Pro Pack'},
            'business': {'price': 4999, 'credits': 200, 'name': 'Business Pack'},
        }
        
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Determine mode
            mode = "Test" if settings.STRIPE_SECRET_KEY.startswith('sk_test') else "Live"
            print(f"🔑 Stripe Mode: {mode}")
            
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f'{plans[plan]["name"]} - {plans[plan]["credits"]} Credits ({mode})',
                        },
                        'unit_amount': plans[plan]['price'],
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri('/dashboard/'),
                cancel_url=request.build_absolute_uri('/buy-credits/'),
                metadata={
                    'user_id': request.user.id,
                    'credits': plans[plan]['credits'],
                    'plan': plan,
                    'mode': mode
                }
            )
            return redirect(checkout_session.url, 303)
            
        except stripe.error.AuthenticationError as e:
            messages.error(request, 'Stripe authentication failed. Check your API keys.')
            print(f"❌ Auth Error: {e}")
            return redirect('buy_credits')
            
        except Exception as e:
            messages.error(request, f'Payment error: {str(e)}')
            print(f"❌ Error: {e}")
            return redirect('buy_credits')
    
    return redirect('buy_credits')