from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from .models import Category, Transaction, TransactionItem
from .forms import TransactionForm, TransactionItemFormSet
from .services import get_month_summary, get_category_totals, get_daily_balance_series
import calendar
from django.db.models import Sum, Q
from django.db.models import Prefetch
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
from django.utils.dateparse import parse_date
from django.utils.formats import date_format
from datetime import datetime


def home(request):
    """
    View para a página inicial que redireciona para o dashboard para usuários autenticados
    ou para a página de login para usuários não autenticados
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    else:
        return redirect('login')


@login_required
def report_transactions(request):
    """
    View para relatório de transações com filtros por data e categoria
    """
    # Check if this is a PDF export request
    if request.GET.get('format') == 'pdf':
        return report_transactions_pdf(request)
    
    transactions = Transaction.objects.filter(owner=request.user).order_by('-date')
    
    # Apply filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    category_id = request.GET.get('category')
    
    if start_date and start_date != 'None':
        transactions = transactions.filter(date__gte=start_date)
    if end_date and end_date != 'None':
        transactions = transactions.filter(date__lte=end_date)
    if category_id and category_id != 'None':
        transactions = transactions.filter(items__category_id=category_id)
        
    # Get categories for filter dropdown - filtrar apenas as categorias do usuário
    categories = Category.objects.filter(user=request.user).order_by('name')
    
    # Calculate totals
    total_income = sum(
        item.amount for transaction in transactions 
        for item in transaction.items.all() 
        if item.category.type == Category.INCOME
    )
    total_expense = sum(
        item.amount for transaction in transactions 
        for item in transaction.items.all() 
        if item.category.type == Category.EXPENSE
    )
    balance = total_income - total_expense
    
    context = {
        'transactions': transactions,
        'categories': categories,
        'start_date': start_date,
        'end_date': end_date,
        'category_id': category_id,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
    }
    
    return render(request, 'core/report_transactions.html', context)


@login_required
def report_transactions_pdf(request):
    """
    Generate PDF for transactions report
    """
    # Get data
    transactions = Transaction.objects.filter(owner=request.user).order_by('-date')
    
    # Apply filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    category_id = request.GET.get('category')
    
    if start_date and start_date != 'None':
        transactions = transactions.filter(date__gte=start_date)
    if end_date and end_date != 'None':
        transactions = transactions.filter(date__lte=end_date)
    if category_id and category_id != 'None':
        transactions = transactions.filter(items__category_id=category_id)
        
    # Calculate totals
    total_income = sum(
        item.amount for transaction in transactions 
        for item in transaction.items.all() 
        if item.category.type == Category.INCOME
    )
    total_expense = sum(
        item.amount for transaction in transactions 
        for item in transaction.items.all() 
        if item.category.type == Category.EXPENSE
    )
    balance = total_income - total_expense
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
    )
    
    # Title
    elements.append(Paragraph("Relatório de Transações", title_style))
    elements.append(Spacer(1, 20))
    
    # Filters info
    filter_text = "Filtros aplicados: "
    if start_date and start_date != 'None':
        parsed_date = parse_date(start_date)
        if parsed_date:
            filter_text += f"De {parsed_date.strftime('%d/%m/%Y')} "
    if end_date and end_date != 'None':
        parsed_date = parse_date(end_date)
        if parsed_date:
            filter_text += f"Até {parsed_date.strftime('%d/%m/%Y')} "
    if category_id and category_id != 'None':
        try:
            category = Category.objects.get(id=category_id)
            filter_text += f"Categoria: {category.name}"
        except Category.DoesNotExist:
            pass
    
    if not (start_date or end_date or category_id) or (start_date == 'None' and end_date == 'None' and category_id == 'None'):
        filter_text += "Nenhum"
        
    elements.append(Paragraph(filter_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Summary table
    summary_data = [
        ['Receitas', 'Despesas', 'Saldo'],
        [f'R$ {total_income:.2f}', f'R$ {total_expense:.2f}', f'R$ {balance:.2f}']
    ]
    
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Transactions table
    if transactions:
        # Table header
        transaction_data = [['Data', 'Descrição', 'Categoria', 'Valor', 'Tipo']]
        
        # Table data
        for transaction in transactions:
            for item in transaction.items.all():
                transaction_data.append([
                    transaction.date.strftime('%d/%m/%Y'),
                    transaction.description,
                    item.category.name,
                    f'R$ {item.amount:.2f}',
                    'Receita' if item.category.type == Category.INCOME else 'Despesa'
                ])
        
        transaction_table = Table(transaction_data)
        transaction_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(Paragraph("Transações", styles['Heading2']))
        elements.append(Spacer(1, 12))
        elements.append(transaction_table)
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_transacoes.pdf"'
    return response


@login_required
def report_transactions_by_category(request):
    """
    View for transactions report grouped by category with date filter
    """
    # Check if this is a PDF export request
    if request.GET.get('format') == 'pdf':
        return report_transactions_by_category_pdf(request)
    
    # Apply date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Build query for transaction items
    items = TransactionItem.objects.filter(transaction__owner=request.user)
    
    if start_date and start_date != 'None':
        items = items.filter(transaction__date__gte=start_date)
    if end_date and end_date != 'None':
        items = items.filter(transaction__date__lte=end_date)
        
    # Group by category and calculate totals
    category_totals = {}
    for item in items.select_related('category', 'transaction'):
        category_name = item.category.name
        category_type = item.category.type
        
        if category_name not in category_totals:
            category_totals[category_name] = {
                'type': category_type,
                'total': 0,
                'count': 0
            }
            
        category_totals[category_name]['total'] += float(item.amount)
        category_totals[category_name]['count'] += 1
    
    # Calculate general totals
    total_income = sum(data['total'] for data in category_totals.values() if data['type'] == Category.INCOME)
    total_expense = sum(data['total'] for data in category_totals.values() if data['type'] == Category.EXPENSE)
    balance = total_income - total_expense
    
    context = {
        'category_totals': category_totals,
        'start_date': start_date,
        'end_date': end_date,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
    }
    
    return render(request, 'core/report_transactions_by_category.html', context)


@login_required
def report_transactions_by_category_pdf(request):
    """
    Generate PDF for transactions by category report
    """
    # Apply date filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Build query for transaction items
    items = TransactionItem.objects.filter(transaction__owner=request.user)
    
    if start_date and start_date != 'None':
        items = items.filter(transaction__date__gte=start_date)
    if end_date and end_date != 'None':
        items = items.filter(transaction__date__lte=end_date)
        
    # Group by category and calculate totals
    category_totals = {}
    for item in items.select_related('category', 'transaction'):
        category_name = item.category.name
        category_type = item.category.type
        
        if category_name not in category_totals:
            category_totals[category_name] = {
                'type': category_type,
                'total': 0,
                'count': 0
            }
            
        category_totals[category_name]['total'] += float(item.amount)
        category_totals[category_name]['count'] += 1
    
    # Calculate general totals
    total_income = sum(data['total'] for data in category_totals.values() if data['type'] == Category.INCOME)
    total_expense = sum(data['total'] for data in category_totals.values() if data['type'] == Category.EXPENSE)
    balance = total_income - total_expense
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
    )
    
    # Title
    elements.append(Paragraph("Relatório de Transações por Categoria", title_style))
    elements.append(Spacer(1, 20))
    
    # Filters info
    filter_text = "Filtros aplicados: "
    if start_date and start_date != 'None':
        parsed_date = parse_date(start_date)
        if parsed_date:
            filter_text += f"De {parsed_date.strftime('%d/%m/%Y')} "
    if end_date and end_date != 'None':
        parsed_date = parse_date(end_date)
        if parsed_date:
            filter_text += f"Até {parsed_date.strftime('%d/%m/%Y')} "
    
    if not (start_date or end_date) or (start_date == 'None' and end_date == 'None'):
        filter_text += "Nenhum"
        
    elements.append(Paragraph(filter_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Summary table
    summary_data = [
        ['Receitas', 'Despesas', 'Saldo'],
        [f'R$ {total_income:.2f}', f'R$ {total_expense:.2f}', f'R$ {balance:.2f}']
    ]
    
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Category table
    if category_totals:
        # Table header
        category_data = [['Categoria', 'Tipo', 'Total', 'Quantidade']]
        
        # Table data
        for category_name, data in category_totals.items():
            category_data.append([
                category_name,
                'Receita' if data['type'] == Category.INCOME else 'Despesa',
                f'R$ {data["total"]:.2f}',
                str(data['count'])
            ])
        
        category_table = Table(category_data)
        category_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(Paragraph("Transações por Categoria", styles['Heading2']))
        elements.append(Spacer(1, 12))
        elements.append(category_table)
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_transacoes_categoria.pdf"'
    return response


@login_required
def report_transactions_by_month(request):
    """
    View for transactions report grouped by month with date and category filters
    """
    # Check if this is a PDF export request
    if request.GET.get('format') == 'pdf':
        return report_transactions_by_month_pdf(request)
    
    # Apply filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    category_id = request.GET.get('category')
    
    # Build query for transaction items
    items = TransactionItem.objects.filter(transaction__owner=request.user)
    
    if start_date and start_date != 'None':
        items = items.filter(transaction__date__gte=start_date)
    if end_date and end_date != 'None':
        items = items.filter(transaction__date__lte=end_date)
    if category_id and category_id != 'None':
        items = items.filter(category_id=category_id)
        
    # Group by month and calculate totals
    monthly_totals = {}
    for item in items.select_related('category', 'transaction'):
        # Get year-month key
        date = item.transaction.date
        month_key = date.strftime('%Y-%m')
        month_name = date.strftime('%m/%Y')
        
        if month_key not in monthly_totals:
            monthly_totals[month_key] = {
                'name': month_name,
                'income': 0,
                'expense': 0,
                'balance': 0,
                'count': 0
            }
            
        if item.category.type == Category.INCOME:
            monthly_totals[month_key]['income'] += float(item.amount)
        else:  # EXPENSE
            monthly_totals[month_key]['expense'] += float(item.amount)
            
        monthly_totals[month_key]['count'] += 1
    
    # Calculate balance for each month
    for data in monthly_totals.values():
        data['balance'] = data['income'] - data['expense']
    
    # Sort by month
    sorted_monthly_totals = sorted(monthly_totals.items(), key=lambda x: x[0])
    
    # Calculate general totals
    total_income = sum(data[1]['income'] for data in sorted_monthly_totals)
    total_expense = sum(data[1]['expense'] for data in sorted_monthly_totals)
    total_balance = total_income - total_expense
    
    # Get categories for filter dropdown - filtrar apenas as categorias do usuário
    categories = Category.objects.filter(user=request.user).order_by('name')
    
    context = {
        'monthly_totals': sorted_monthly_totals,
        'categories': categories,
        'start_date': start_date,
        'end_date': end_date,
        'category_id': category_id,
        'total_income': total_income,
        'total_expense': total_expense,
        'total_balance': total_balance,
    }
    
    return render(request, 'core/report_transactions_by_month.html', context)


@login_required
def report_transactions_by_month_pdf(request):
    """
    Generate PDF for transactions by month report
    """
    # Apply filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    category_id = request.GET.get('category')
    
    # Build query for transaction items
    items = TransactionItem.objects.filter(transaction__owner=request.user)
    
    if start_date and start_date != 'None':
        items = items.filter(transaction__date__gte=start_date)
    if end_date and end_date != 'None':
        items = items.filter(transaction__date__lte=end_date)
    if category_id and category_id != 'None':
        items = items.filter(category_id=category_id)
        
    # Group by month and calculate totals
    monthly_totals = {}
    for item in items.select_related('category', 'transaction'):
        # Get year-month key
        date = item.transaction.date
        month_key = date.strftime('%Y-%m')
        month_name = date.strftime('%m/%Y')
        
        if month_key not in monthly_totals:
            monthly_totals[month_key] = {
                'name': month_name,
                'income': 0,
                'expense': 0,
                'balance': 0,
                'count': 0
            }
            
        if item.category.type == Category.INCOME:
            monthly_totals[month_key]['income'] += float(item.amount)
        else:  # EXPENSE
            monthly_totals[month_key]['expense'] += float(item.amount)
            
        monthly_totals[month_key]['count'] += 1
    
    # Calculate balance for each month
    for data in monthly_totals.values():
        data['balance'] = data['income'] - data['expense']
    
    # Sort by month
    sorted_monthly_totals = sorted(monthly_totals.items(), key=lambda x: x[0])
    
    # Calculate general totals
    total_income = sum(data[1]['income'] for data in sorted_monthly_totals)
    total_expense = sum(data[1]['expense'] for data in sorted_monthly_totals)
    total_balance = total_income - total_expense
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
    )
    
    # Title
    elements.append(Paragraph("Relatório de Transações por Mês", title_style))
    elements.append(Spacer(1, 20))
    
    # Filters info
    filter_text = "Filtros aplicados: "
    if start_date and start_date != 'None':
        parsed_date = parse_date(start_date)
        if parsed_date:
            filter_text += f"De {parsed_date.strftime('%d/%m/%Y')} "
    if end_date and end_date != 'None':
        parsed_date = parse_date(end_date)
        if parsed_date:
            filter_text += f"Até {parsed_date.strftime('%d/%m/%Y')} "
    if category_id and category_id != 'None':
        try:
            category = Category.objects.get(id=category_id)
            filter_text += f"Categoria: {category.name}"
        except Category.DoesNotExist:
            pass
    
    if not (start_date or end_date or category_id) or (start_date == 'None' and end_date == 'None' and category_id == 'None'):
        filter_text += "Nenhum"
        
    elements.append(Paragraph(filter_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Summary table
    summary_data = [
        ['Receitas', 'Despesas', 'Saldo'],
        [f'R$ {total_income:.2f}', f'R$ {total_expense:.2f}', f'R$ {total_balance:.2f}']
    ]
    
    summary_table = Table(summary_data)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Monthly table
    if sorted_monthly_totals:
        # Table header
        monthly_data = [['Mês', 'Receitas', 'Despesas', 'Saldo', 'Quantidade']]
        
        # Table data
        for month_key, data in sorted_monthly_totals:
            monthly_data.append([
                data['name'],
                f'R$ {data["income"]:.2f}',
                f'R$ {data["expense"]:.2f}',
                f'R$ {data["balance"]:.2f}',
                str(data['count'])
            ])
        
        monthly_table = Table(monthly_data)
        monthly_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(Paragraph("Transações por Mês", styles['Heading2']))
        elements.append(Spacer(1, 12))
        elements.append(monthly_table)
    
    # Build PDF
    doc.build(elements)
    
    # Return PDF
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="relatorio_transacoes_mes.pdf"'
    return response


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'core/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        queryset = Category.objects.filter(user=self.request.user)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'type']
    success_url = reverse_lazy('category_list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'Categoria criada com sucesso!')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'type']
    success_url = reverse_lazy('category_list')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Categoria atualizada com sucesso!')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'core/category_confirm_delete.html'
    success_url = reverse_lazy('category_list')

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        # Verifica se a categoria está sendo usada
        if TransactionItem.objects.filter(category=category).exists():
            messages.error(self.request, 'Não é possível excluir esta categoria pois ela está sendo usada em transações.')
            return redirect('category_list')
        messages.success(self.request, 'Categoria excluída com sucesso!')
        return super().delete(request, *args, **kwargs)


class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'core/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20

    def get_queryset(self):
        queryset = Transaction.objects.filter(owner=self.request.user)
        
        # Pesquisa por descrição
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(description__icontains=search)
            
        # Filtra por intervalo de datas
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        # Filtra por tipo (receita/despesa)
        transaction_type = self.request.GET.get('type')
        if transaction_type:
            if transaction_type == 'INCOME':
                queryset = queryset.filter(items__category__type='INCOME')
            elif transaction_type == 'EXPENSE':
                queryset = queryset.filter(items__category__type='EXPENSE')
                
        return queryset.distinct()


class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'core/transaction_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = TransactionItemFormSet(self.request.POST, form_kwargs={'user': self.request.user})
        else:
            context['formset'] = TransactionItemFormSet(form_kwargs={'user': self.request.user})
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        # Verifica se o formset é válido e tem pelo menos um item
        if formset.is_valid():
            # Verifica se pelo menos um item está preenchido
            has_items = any(formset.cleaned_data for form in formset if form.cleaned_data and not form.cleaned_data.get('DELETE', False))
            if not has_items:
                form.add_error(None, 'É necessário adicionar pelo menos um item à transação.')
                return self.form_invalid(form)
            
            # Salva transação e itens
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.owner = self.request.user
                self.object.save()
                
                # Salva formset
                formset.instance = self.object
                formset.save()
                
                # Calcula o valor total
                total = 0
                for item in self.object.items.all():
                    if item.category.type == 'INCOME':
                        total += item.amount
                    else:  # EXPENSE
                        total -= item.amount
                self.object.total_amount = total
                self.object.save()
                
                messages.success(self.request, 'Transação criada com sucesso!')
                return redirect('transaction_list')
        else:
            return self.form_invalid(form)


class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'core/transaction_form.html'

    def get_queryset(self):
        return Transaction.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = TransactionItemFormSet(self.request.POST, instance=self.object, form_kwargs={'user': self.request.user})
        else:
            context['formset'] = TransactionItemFormSet(instance=self.object, form_kwargs={'user': self.request.user})
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        # Verifica se o formset é válido
        if formset.is_valid():
            # Verifica se pelo menos um item está preenchido
            has_items = any(formset.cleaned_data for form in formset if form.cleaned_data and not form.cleaned_data.get('DELETE', False))
            if not has_items:
                form.add_error(None, 'É necessário adicionar pelo menos um item à transação.')
                return self.form_invalid(form)
            
            # Salva transação e itens
            with transaction.atomic():
                self.object = form.save()
                
                # Salva formset
                formset.instance = self.object
                formset.save()
                
                # Calcula o valor total
                total = 0
                for item in self.object.items.all():
                    if item.category.type == 'INCOME':
                        total += item.amount
                    else:  # EXPENSE
                        total -= item.amount
                self.object.total_amount = total
                self.object.save()
                
                messages.success(self.request, 'Transação atualizada com sucesso!')
                return redirect('transaction_list')
        else:
            return self.form_invalid(form)


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = 'core/transaction_detail.html'
    context_object_name = 'transaction'

    def get_queryset(self):
        return Transaction.objects.filter(owner=self.request.user)


class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = 'core/transaction_confirm_delete.html'
    success_url = reverse_lazy('transaction_list')

    def get_queryset(self):
        return Transaction.objects.filter(owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Transação excluída com sucesso!')
        return super().delete(request, *args, **kwargs)


@login_required
def dashboard(request):
    # Obtém o mês e ano atual
    today = timezone.now().date()
    year = today.year
    month = today.month
    
    # Nomes dos meses em português
    portuguese_month_names = [
        '', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    # Obtém os dados do resumo
    summary = get_month_summary(request.user, year, month)
    
    # Obtém os totais por categoria
    category_totals = get_category_totals(request.user, year, month)
    
    # Obtém a série de saldo diário
    daily_balance = get_daily_balance_series(request.user, year, month)
    
    context = {
        'summary': summary,
        'category_totals': category_totals,
        'daily_balance': daily_balance,
        'month_name': portuguese_month_names[month],
        'year': year,
    }
    
    return render(request, 'core/dashboard.html', context)