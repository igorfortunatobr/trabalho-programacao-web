from django.db.models import Sum, Q
from django.utils import timezone
from .models import Transaction, TransactionItem, Category
from decimal import Decimal
from collections import defaultdict
import calendar
import json


def get_month_summary(user, year, month):
    """
    Get income, expense and balance for a specific month
    """
    # First day of the month
    start_date = timezone.datetime(year, month, 1).date()
    # Last day of the month
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day).date()
    
    # Get all transactions for the user in the specified month
    transactions = Transaction.objects.filter(
        owner=user,
        date__range=(start_date, end_date)
    )
    
    # Calculate totals
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
    Get totals by category for a specific month
    Returns a dictionary that can be easily converted to JSON
    """
    # First day of the month
    start_date = timezone.datetime(year, month, 1).date()
    # Last day of the month
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day).date()
    
    # Get all transaction items for the user in the specified month
    transaction_items = TransactionItem.objects.filter(
        transaction__owner=user,
        transaction__date__range=(start_date, end_date)
    ).select_related('category')
    
    # Group by category
    category_totals = defaultdict(Decimal)
    
    for item in transaction_items:
        if item.category.type == Category.INCOME:
            category_totals[item.category.name] += item.amount
        else:  # EXPENSE
            category_totals[item.category.name] += item.amount
    
    # Convert to regular dict and float values for JSON serialization
    result = {}
    for key, value in category_totals.items():
        result[key] = float(value)
    
    return result


def get_daily_balance_series(user, year, month):
    """
    Get daily balance series for a specific month
    Returns a list that can be easily converted to JSON
    """
    # First day of the month
    start_date = timezone.datetime(year, month, 1).date()
    # Last day of the month
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day).date()
    
    # Get all transaction items for the user in the specified month
    transaction_items = TransactionItem.objects.filter(
        transaction__owner=user,
        transaction__date__range=(start_date, end_date)
    ).select_related('category', 'transaction')
    
    # Group by date and calculate daily amounts
    daily_amounts = defaultdict(Decimal)
    
    for item in transaction_items:
        date = item.transaction.date
        if item.category.type == Category.INCOME:
            daily_amounts[date] += item.amount
        else:  # EXPENSE
            daily_amounts[date] -= item.amount
    
    # Calculate cumulative balance
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