from django import forms
from .models import Request, Service, Client


class RequestForm(forms.ModelForm):
    company_name = forms.CharField(
        max_length=255, label="Название компании"
    )
    contact_person = forms.CharField(
        max_length=255, label="Контактное лицо", required=False
    )
    phone = forms.CharField(
        max_length=20, label="Телефон"
    )
    email = forms.EmailField(
        label="Email", required=False
    )
    object_type = forms.CharField(
        max_length=100, label="Тип объекта"
    )
    object_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        label="Адрес объекта", required=False
    )
    area = forms.DecimalField(
        label="Площадь, м²", required=False
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Опишите задачу, объект, особенности проекта...'
        }),
        label="Описание задачи",
        required=False
    )
    attached_file = forms.FileField(
        label="📎 Прикрепить файл (PDF, DOCX и т.д.)", required=False
    )

    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Выберите услуги",
        required=False
    )

    class Meta:
        model = Request
        fields = [
            'company_name', 'contact_person', 'phone', 'email',
            'object_type', 'object_address', 'area',
            'description', 'services', 'attached_file'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Загружаем услуги только с КП (если это бизнес-логика)
        self.fields['services'].queryset = Service.objects.filter(has_kp=True)

    def clean_phone(self):
        """Приводим телефон к нормализованному виду."""
        import re
        phone = self.cleaned_data.get('phone', '').strip()
        norm = re.sub(r'[^\d+]', '', phone)
        if not norm:
            raise forms.ValidationError("Введите корректный номер телефона.")
        return norm

    def save(self, commit=True):
        """
        Сохраняем форму:
        1️⃣ создаём или находим клиента;
        2️⃣ создаём заявку (Request) и связываем её с клиентом;
        3️⃣ добавляем выбранные услуги.
        """
        data = self.cleaned_data

        # === Клиент ===
        client, created = Client.objects.get_or_create(
            company_name=data['company_name'].strip(),
            defaults={
                'contact_person': data.get('contact_person', ''),
                'phone': data.get('phone', ''),
                'email': data.get('email', ''),
            }
        )

        # Если клиент уже существует — обновляем его контакты
        if not created:
            updated = False
            for field in ['contact_person', 'phone', 'email']:
                if data.get(field) and getattr(client, field) != data.get(field):
                    setattr(client, field, data.get(field))
                    updated = True
            if updated:
                client.save()

        # === Заявка ===
        request = Request(
            client=client,
            object_type=data.get('object_type', ''),
            object_address=data.get('object_address', ''),
            area=data.get('area'),
            description=data.get('description', ''),
            attached_file=data.get('attached_file'),
            status='new'
        )

        if commit:
            request.save()
            if data.get('services'):
                request.services.set(data['services'])

        return request
