from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Category, Transaction, TransactionItem
from django.utils import timezone
import random
from decimal import Decimal


class Command(BaseCommand):
    help = 'Preenche o banco de dados com dados de exemplo'

    def handle(self, *args, **options):
        # Cria usuário demo
        if not User.objects.filter(username='demo').exists():
            user = User.objects.create_user(
                username='demo',
                email='demo@demo.com',
                password='123456'
            )
            self.stdout.write(
                self.style.SUCCESS('Usuário demo criado com sucesso: demo@demo.com / 123456')
            )
        else:
            user = User.objects.get(username='demo')
            self.stdout.write(
                self.style.WARNING('Usuário demo já existe')
            )

        # Cria categorias
        categories_data = [
            {'name': 'Receitas', 'type': Category.INCOME},
            {'name': 'Despesas', 'type': Category.EXPENSE},
            {'name': 'Luz', 'type': Category.EXPENSE},
            {'name': 'Água', 'type': Category.EXPENSE},
            {'name': 'Salário', 'type': Category.INCOME},
            {'name': 'Alimentação', 'type': Category.EXPENSE},
            {'name': 'Transporte', 'type': Category.EXPENSE},
            {'name': 'Lazer', 'type': Category.EXPENSE},
            {'name': 'Saúde', 'type': Category.EXPENSE},
            {'name': 'Educação', 'type': Category.EXPENSE},
        ]

        categories = []
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={'type': cat_data['type']}
            )
            categories.append(category)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Categoria criada: {category.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Categoria já existe: {category.name}')
                )

        # Cria transações de exemplo para o mês atual
        today = timezone.now().date()
        year = today.year
        month = today.month

        # Exclui transações existentes do usuário demo no mês atual para evitar duplicatas
        Transaction.objects.filter(
            owner=user,
            date__year=year,
            date__month=month
        ).delete()

        # Cria 20 transações de exemplo
        descriptions = [
            'Compra no supermercado', 'Pagamento de conta de luz', 'Salário mensal',
            'Consulta médica', 'Curso online', 'Cinema', 'Combustível',
            'Restaurante', 'Compra de roupas', 'Hotéis', 'Viagem', 'Presente',
            'Manutenção do carro', 'Internet', 'Telefone', 'Academia',
            'Livros', 'Eletrônicos', 'Móveis', 'Decoração'
        ]

        for i in range(20):
            # Data aleatória no mês atual
            day = random.randint(1, 28)  # Evita problemas com fevereiro
            date = timezone.datetime(year, month, day).date()

            # Cria transação
            transaction = Transaction.objects.create(
                description=random.choice(descriptions),
                date=date,
                owner=user
            )

            # Cria 1-3 itens para esta transação
            num_items = random.randint(1, 3)
            total_amount = Decimal('0.00')

            for j in range(num_items):
                category = random.choice(categories)
                amount = Decimal(random.randint(10, 500)) + Decimal(random.randint(0, 99)) / 100

                TransactionItem.objects.create(
                    transaction=transaction,
                    category=category,
                    amount=amount
                )

                # Calcula o valor total baseado no tipo da categoria
                if category.type == Category.INCOME:
                    total_amount += amount
                else:
                    total_amount -= amount

            # Atualiza o valor total da transação
            transaction.total_amount = total_amount
            transaction.save()

        self.stdout.write(
            self.style.SUCCESS('Banco de dados preenchido com sucesso com dados de exemplo')
        )