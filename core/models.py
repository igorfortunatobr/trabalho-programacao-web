from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal


class Category(models.Model):
    INCOME = 'INCOME'
    EXPENSE = 'EXPENSE'
    CATEGORY_TYPES = [
        (INCOME, 'Receita'),
        (EXPENSE, 'Despesa'),
    ]

    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=10, choices=CATEGORY_TYPES)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'


class Transaction(models.Model):
    description = models.CharField(max_length=200)
    date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.description} - {self.date}"

    class Meta:
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'


class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, related_name='items', on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    def __str__(self):
        return f"{self.category.name} - {self.amount}"

    class Meta:
        verbose_name = 'Item de Transação'
        verbose_name_plural = 'Itens de Transação'