# main/forms.py
from django import forms
from .models import Request, Client, Service

class RequestForm(forms.ModelForm):
    company_name = forms.CharField(max_length=255, label="Название компании")
    contact_person = forms.CharField(max_length=255, label="Контактное лицо")
    phone = forms.CharField(max_length=20, label="Телефон")
    email = forms.EmailField(label="Email")
    
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(has_kp=True),
        widget=forms.CheckboxSelectMultiple,
        label="Выберите услуги"
    )
    
    class Meta:
        model = Request
        fields = ['company_name', 'contact_person', 'phone', 'email', 
                 'object_type', 'object_description', 'services', 'attached_file']
        widgets = {
            'object_description': forms.Textarea(attrs={'rows': 4}),
        }