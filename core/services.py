from django.db.models import Sum, Q
from django.utils import timezone
from .models import Transaction, TransactionItem, Category
from decimal import Decimal
from collections import defaultdict
import calendar
import json


def get_month_summary(user, year, month):
    """
    Obtém receita, despesa e saldo para um mês específico
    """
    # Primeiro dia do mês
    start_date = timezone.datetime(year, month, 1).date()
    # Último dia do mês
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day).date()
    
    # Obtém todas as transações do usuário no mês especificado
    transactions = Transaction.objects.filter(
        owner=user,
        date__range=(start_date, end_date)
    )
    
    # Calcula os totais
    total_income = Decimal('0.00')
    total_expense = Decimal('0.00')
    
    for transaction in transactions:
        for item in transaction.items.all():
            if item.category.type == Category.INCOME:
                total_income += item.amount
            else:  # EXPENSE
                total_expense += item.amount
    
    balance = total_income - total_expense
    
    return {
        'income': total_income,
        'expense': total_expense,
        'balance': balance
    }


def get_category_totals(user, year, month):
    """
    Obtém totais por categoria para um mês específico
    Retorna um dicionário que pode ser facilmente convertido para JSON
    """
    # Primeiro dia do mês
    start_date = timezone.datetime(year, month, 1).date()
    # Último dia do mês
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day).date()
    
    # Obtém todos os itens de transação do usuário no mês especificado
    transaction_items = TransactionItem.objects.filter(
        transaction__owner=user,
        transaction__date__range=(start_date, end_date)
    ).select_related('category')
    
    # Agrupa por categoria
    category_totals = defaultdict(Decimal)
    
    for item in transaction_items:
        if item.category.type == Category.INCOME:
            category_totals[item.category.name] += item.amount
        else:  # EXPENSE
            category_totals[item.category.name] += item.amount
    
    # Converte para dict regular e valores float para serialização JSON
    result = {}
    for key, value in category_totals.items():
        result[key] = float(value)
    
    return result


def get_daily_balance_series(user, year, month):
    """
    Obtém a série de saldo diário para um mês específico
    Retorna uma lista que pode ser facilmente convertida para JSON
    """
    # Primeiro dia do mês
    start_date = timezone.datetime(year, month, 1).date()
    # Último dia do mês
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day).date()
    
    # Obtém todos os itens de transação do usuário no mês especificado
    transaction_items = TransactionItem.objects.filter(
        transaction__owner=user,
        transaction__date__range=(start_date, end_date)
    ).select_related('category', 'transaction')
    
    # Agrupa por data e calcula valores diários
    daily_amounts = defaultdict(Decimal)
    
    for item in transaction_items:
        date = item.transaction.date
        if item.category.type == Category.INCOME:
            daily_amounts[date] += item.amount
        else:  # EXPENSE
            daily_amounts[date] -= item.amount
    
    # Calcula o saldo cumulativo
    dates = sorted(daily_amounts.keys())
    balance_series = []
    cumulative_balance = Decimal('0.00')
    
    for date in dates:
        cumulative_balance += daily_amounts[date]
        balance_series.append({
            'date': date.strftime('%Y-%m-%d'),
            'balance': float(cumulative_balance)
        })
    
    return balance_series