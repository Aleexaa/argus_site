from django.core.management.base import BaseCommand
from crm.utils import ClientDeduplicator

class Command(BaseCommand):
    help = 'Объединяет дублирующихся клиентов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Автоматически объединить все дубликаты',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать дубликаты без объединения',
        )
        parser.add_argument(
            '--aggressive',
            action='store_true',
            help='Агрессивный поиск дубликатов',
        )

    def handle(self, *args, **options):
        deduplicator = ClientDeduplicator()
        
        if options['dry_run']:
            self.stdout.write('=== РЕЖИМ ПРОСМОТРА (без изменений) ===')
            
            if options['aggressive']:
                groups = deduplicator.find_similar_clients()
            else:
                groups = deduplicator.find_duplicate_groups()
            
            if not groups:
                self.stdout.write(
                    self.style.SUCCESS('Дубликаты не найдены!')
                )
                return
            
            for group in groups:
                self.stdout.write(
                    f"\n{self.style.WARNING('Дубликаты по ' + group['type'] + ':')} {group['key']}"
                )
                for client in group['clients']:
                    self.stdout.write(
                        f"  - {client.company_name} (ID: {client.id}, тел: {client.phone}, email: {client.email}, заявок: {client.requests.count()})"
                    )
            
            total_duplicates = sum(len(group['clients']) - 1 for group in groups)
            self.stdout.write(
                f"\n{self.style.WARNING('Всего групп дубликатов:')} {len(groups)}"
            )
            self.stdout.write(
                f"{self.style.WARNING('Всего дубликатов для объединения:')} {total_duplicates}"
            )
            
        elif options['auto']:
            self.stdout.write('=== АВТОМАТИЧЕСКОЕ ОБЪЕДИНЕНИЕ ===')
            merged_count = deduplicator.auto_deduplicate()
            
            if merged_count == 0:
                self.stdout.write(
                    self.style.SUCCESS('Дубликаты не найдены!')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Объединено {merged_count} дубликатов клиентов!')
                )
                
        else:
            self.stdout.write('Используйте:')
            self.stdout.write('  --dry-run для просмотра дубликатов')
            self.stdout.write('  --dry-run --aggressive для агрессивного поиска')
            self.stdout.write('  --auto для автоматического объединения')