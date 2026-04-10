from django import forms
from .models import Client, Feedback
from .utils import ClientDeduplicator

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['company_name', 'contact_person', 'phone', 'email']
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent',
                'placeholder': 'Название компании'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent',
                'placeholder': 'Контактное лицо'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent',
                'placeholder': '+7 (XXX) XXX-XX-XX'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gold focus:border-transparent',
                'placeholder': 'email@example.com'
            }),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            normalized_phone = ClientDeduplicator.normalize_phone(phone)
            
            # Ищем похожие телефоны
            similar_phones = Client.objects.filter(
                phone__contains=normalized_phone
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if similar_phones.exists():
                similar_companies = [c.company_name for c in similar_phones[:3]]  # Показываем первые 3
                raise forms.ValidationError(
                    f'Похожий телефон уже используется у: {", ".join(similar_companies)}'
                )
            
            return normalized_phone
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            normalized_email = ClientDeduplicator.normalize_email(email)
            
            duplicates = Client.objects.filter(
                email__iexact=normalized_email
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if duplicates.exists():
                similar_companies = [c.company_name for c in duplicates[:3]]
                raise forms.ValidationError(
                    f'Этот email уже используется у: {", ".join(similar_companies)}'
                )
            
            return normalized_email
        return email
    
class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['name', 'contact', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 transition-colors',
                'placeholder': 'Иван Иванов'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 transition-colors',
                'placeholder': '+7 (___) ___-__-__ или email@example.com'
            }),
            'message': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 transition-colors resize-none',
                'placeholder': 'Ваше сообщение...',
                'rows': 4
            }),
        }