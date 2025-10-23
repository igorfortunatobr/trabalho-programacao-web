from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from .models import Category, Transaction, TransactionItem
from .services import get_month_summary, get_category_totals, get_daily_balance_series


class CategoryModelTest(TestCase):
    def setUp(self):
        self.category_income = Category.objects.create(
            name='Salário',
            type=Category.INCOME
        )
        self.category_expense = Category.objects.create(
            name='Aluguel',
            type=Category.EXPENSE
        )

    def test_category_creation(self):
        self.assertEqual(self.category_income.name, 'Salário')
        self.assertEqual(self.category_income.type, Category.INCOME)
        self.assertEqual(self.category_expense.name, 'Aluguel')
        self.assertEqual(self.category_expense.type, Category.EXPENSE)

    def test_category_str_representation(self):
        self.assertEqual(str(self.category_income), 'Salário')
        self.assertEqual(str(self.category_expense), 'Aluguel')


class TransactionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.transaction = Transaction.objects.create(
            description='Transação de teste',
            date=timezone.now().date(),
            owner=self.user
        )

    def test_transaction_creation(self):
        self.assertEqual(self.transaction.description, 'Transação de teste')
        self.assertEqual(self.transaction.owner, self.user)
        self.assertEqual(self.transaction.total_amount, 0)

    def test_transaction_str_representation(self):
        expected_str = f"Transação de teste - {self.transaction.date}"
        self.assertEqual(str(self.transaction), expected_str)


class TransactionItemModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Alimentação',
            type=Category.EXPENSE
        )
        self.transaction = Transaction.objects.create(
            description='Compra no mercado',
            date=timezone.now().date(),
            owner=self.user
        )
        self.transaction_item = TransactionItem.objects.create(
            transaction=self.transaction,
            category=self.category,
            amount=Decimal('150.75')
        )

    def test_transaction_item_creation(self):
        self.assertEqual(self.transaction_item.transaction, self.transaction)
        self.assertEqual(self.transaction_item.category, self.category)
        self.assertEqual(self.transaction_item.amount, Decimal('150.75'))

    def test_transaction_item_str_representation(self):
        expected_str = f"Alimentação - 150.75"
        self.assertEqual(str(self.transaction_item), expected_str)


class ServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category_income = Category.objects.create(
            name='Salário',
            type=Category.INCOME
        )
        self.category_expense = Category.objects.create(
            name='Aluguel',
            type=Category.EXPENSE
        )
        self.transaction = Transaction.objects.create(
            description='Transação de teste',
            date=timezone.now().date(),
            owner=self.user
        )
        TransactionItem.objects.create(
            transaction=self.transaction,
            category=self.category_income,
            amount=Decimal('3000.00')
        )
        TransactionItem.objects.create(
            transaction=self.transaction,
            category=self.category_expense,
            amount=Decimal('1500.00')
        )

    def test_get_month_summary(self):
        today = timezone.now().date()
        summary = get_month_summary(self.user, today.year, today.month)
        
        self.assertEqual(summary['income'], Decimal('3000.00'))
        self.assertEqual(summary['expense'], Decimal('1500.00'))
        self.assertEqual(summary['balance'], Decimal('1500.00'))

    def test_get_category_totals(self):
        today = timezone.now().date()
        category_totals = get_category_totals(self.user, today.year, today.month)
        
        self.assertEqual(category_totals['Salário'], Decimal('3000.00'))
        self.assertEqual(category_totals['Aluguel'], Decimal('1500.00'))

    def test_get_daily_balance_series(self):
        today = timezone.now().date()
        daily_balance = get_daily_balance_series(self.user, today.year, today.month)
        
        self.assertEqual(len(daily_balance), 1)
        self.assertEqual(daily_balance[0]['balance'], 1500.0)


class FormValidationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Teste',
            type=Category.EXPENSE
        )

    def test_transaction_item_amount_validation(self):
        from .forms import TransactionItemForm
        
        # Teste de valor inválido (menor que 0,01)
        form_data = {
            'category': self.category.id,
            'amount': '0.00'
        }
        form = TransactionItemForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Teste de valor válido
        form_data = {
            'category': self.category.id,
            'amount': '10.50'
        }
        form = TransactionItemForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_transaction_date_validation(self):
        from .forms import TransactionForm
        from django.utils import timezone
        
        # Teste de data futura (deve ser inválida)
        future_date = timezone.now().date() + timezone.timedelta(days=1)
        form_data = {
            'description': 'Transação futura',
            'date': future_date
        }
        form = TransactionForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Teste de data atual (deve ser válida)
        form_data = {
            'description': 'Transação hoje',
            'date': timezone.now().date()
        }
        form = TransactionForm(data=form_data)
        self.assertTrue(form.is_valid())