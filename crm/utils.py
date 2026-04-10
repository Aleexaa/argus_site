from django.db import transaction
import re

class ClientDeduplicator:
    """
    Утилита для поиска и объединения дубликатов клиентов
    """
    
    @staticmethod
    def normalize_phone(phone):
        """Нормализация телефонного номера - более агрессивная"""
        if not phone:
            return None
        
        # Оставляем только цифры
        digits = re.sub(r'\D', '', str(phone))
        
        # Если номер пустой после очистки
        if not digits:
            return None
            
        # Для российских номеров: оставляем последние 10 цифр
        if len(digits) == 11 and digits[0] in ['7', '8']:
            return digits[1:]  # Убираем 7 или 8
        elif len(digits) == 10:
            return digits
        elif len(digits) > 10:
            return digits[-10:]  # Берем последние 10 цифр
        else:
            return digits  # Возвращаем как есть для коротких номеров
    
    @staticmethod
    def normalize_email(email):
        """Нормализация email"""
        if not email:
            return None
        return email.lower().strip()
    
    @staticmethod
    def find_duplicate_groups():
        """Находит группы дубликатов по разным критериям - улучшенная версия"""
        from .models import Client
        clients = list(Client.objects.all())
        groups = {}
        
        print(f"Всего клиентов в базе: {len(clients)}")
        
        for i, client in enumerate(clients):
            # Нормализуем данные клиента
            phone_key = ClientDeduplicator.normalize_phone(client.phone)
            email_key = ClientDeduplicator.normalize_email(client.email)
            company_key = client.company_name.lower().strip() if client.company_name else None
            
            print(f"Клиент {i+1}: {client.company_name}, тел: {client.phone} -> {phone_key}, email: {client.email} -> {email_key}")
            
            # Создаем составные ключи для лучшей группировки
            keys_to_check = []
            
            # Ключ по телефону
            if phone_key:
                keys_to_check.append(f"phone:{phone_key}")
            
            # Ключ по email
            if email_key:
                keys_to_check.append(f"email:{email_key}")
            
            # Ключ по компании + телефон (первые 5 цифр)
            if company_key and phone_key:
                short_phone = phone_key[:7] if len(phone_key) >= 7 else phone_key
                keys_to_check.append(f"company_phone:{company_key}:{short_phone}")
            
            # Ключ по компании + email
            if company_key and email_key:
                keys_to_check.append(f"company_email:{company_key}:{email_key}")
            
            # Добавляем клиента во все подходящие группы
            for key in keys_to_check:
                if key not in groups:
                    groups[key] = {'type': key.split(':')[0], 'clients': []}
                
                # Проверяем, нет ли уже этого клиента в группе
                if client not in groups[key]['clients']:
                    groups[key]['clients'].append(client)
        
        # Фильтруем только группы с дубликатами
        duplicate_groups = {k: v for k, v in groups.items() if len(v['clients']) > 1}
        
        print(f"Найдено групп дубликатов: {len(duplicate_groups)}")
        
        return duplicate_groups
    
    @staticmethod
    def find_similar_clients():
        """Находит похожих клиентов по различным критериям"""
        from .models import Client
        clients = list(Client.objects.all())
        similar_groups = []
        
        # Создаем индекс для быстрого поиска
        phone_index = {}
        email_index = {}
        company_index = {}
        
        # Строим индексы
        for client in clients:
            # Индекс по телефону
            phone_key = ClientDeduplicator.normalize_phone(client.phone)
            if phone_key:
                if phone_key not in phone_index:
                    phone_index[phone_key] = []
                phone_index[phone_key].append(client)
            
            # Индекс по email
            email_key = ClientDeduplicator.normalize_email(client.email)
            if email_key:
                if email_key not in email_index:
                    email_index[email_key] = []
                email_index[email_key].append(client)
            
            # Индекс по компании (похожие названия)
            if client.company_name:
                company_name = client.company_name.lower().strip()
                # Создаем несколько вариантов ключа для поиска похожих названий
                company_keys = [company_name]
                # Без ООО/ОАО и т.д.
                clean_name = re.sub(r'\b(ооо|оао|зао|пао|ип)\b', '', company_name, flags=re.IGNORECASE).strip()
                if clean_name and clean_name != company_name:
                    company_keys.append(clean_name)
                
                for key in company_keys:
                    if key not in company_index:
                        company_index[key] = []
                    company_index[key].append(client)
        
        # Ищем дубликаты по телефону
        for phone, phone_clients in phone_index.items():
            if len(phone_clients) > 1:
                similar_groups.append({
                    'type': 'phone',
                    'key': phone,
                    'clients': phone_clients
                })
        
        # Ищем дубликаты по email
        for email, email_clients in email_index.items():
            if len(email_clients) > 1:
                similar_groups.append({
                    'type': 'email', 
                    'key': email,
                    'clients': email_clients
                })
        
        # Ищем дубликаты по названию компании
        for company, company_clients in company_index.items():
            if len(company_clients) > 1:
                similar_groups.append({
                    'type': 'company',
                    'key': company,
                    'clients': company_clients
                })
        
        return similar_groups
    
    @staticmethod
    def merge_clients(clients):
        """Объединяет несколько клиентов в одного"""
        if len(clients) < 2:
            return clients[0] if clients else None
        
        from .models import Client
        
        # Выбираем "главного" клиента (с наибольшим количеством заявок или самым старым)
        main_client = None
        for client in clients:
            if main_client is None or client.requests.count() > main_client.requests.count():
                main_client = client
            # Если количество заявок одинаковое, берем самого старого
            elif client.requests.count() == main_client.requests.count():
                if client.created_at < main_client.created_at:
                    main_client = client
        
        other_clients = [c for c in clients if c.id != main_client.id]
        
        print(f"Объединяем {len(other_clients)} клиентов в {main_client.company_name}")
        
        with transaction.atomic():
            # Переносим заявки от дубликатов к главному клиенту
            for client in other_clients:
                for request in client.requests.all():
                    request.client = main_client
                    request.save()
            
            # Обновляем данные главного клиента, если нужно
            updated = False
            for client in other_clients:
                if not main_client.contact_person and client.contact_person:
                    main_client.contact_person = client.contact_person
                    updated = True
                if not main_client.email and client.email:
                    main_client.email = client.email
                    updated = True
                # Можно добавить и другие поля
            
            if updated:
                main_client.save()
            
            # Удаляем дубликаты
            for client in other_clients:
                print(f"Удаляем клиента: {client.company_name} (ID: {client.id})")
                client.delete()
        
        return main_client
    
    @staticmethod
    def auto_deduplicate():
        """Автоматическое объединение всех дубликатов"""
        groups = ClientDeduplicator.find_similar_clients()
        merged_count = 0
        
        print(f"Найдено {len(groups)} групп для объединения")
        
        # Сначала объединяем по телефону (самый надежный критерий)
        phone_groups = [g for g in groups if g['type'] == 'phone']
        for group in phone_groups:
            if len(group['clients']) > 1:
                print(f"Объединяем {len(group['clients'])} клиентов по телефону: {group['key']}")
                ClientDeduplicator.merge_clients(group['clients'])
                merged_count += len(group['clients']) - 1
        
        # Затем по email
        email_groups = [g for g in groups if g['type'] == 'email']
        for group in email_groups:
            if len(group['clients']) > 1:
                print(f"Объединяем {len(group['clients'])} клиентов по email: {group['key']}")
                ClientDeduplicator.merge_clients(group['clients'])
                merged_count += len(group['clients']) - 1
        
        return merged_count