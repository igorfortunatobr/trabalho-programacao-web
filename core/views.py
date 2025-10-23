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


def home(request):
    """
    View for the home page that redirects to dashboard for authenticated users
    or to login page for unauthenticated users
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    else:
        return redirect('login')


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'core/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        queryset = Category.objects.all()
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
        messages.success(self.request, 'Categoria criada com sucesso!')
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    template_name = 'core/category_form.html'
    fields = ['name', 'type']
    success_url = reverse_lazy('category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Categoria atualizada com sucesso!')
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'core/category_confirm_delete.html'
    success_url = reverse_lazy('category_list')

    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        # Check if category is being used
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
        
        # Search by description
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(description__icontains=search)
            
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
            
        # Filter by type (income/expense)
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
            context['formset'] = TransactionItemFormSet(self.request.POST)
        else:
            context['formset'] = TransactionItemFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        # Check if formset is valid and has at least one item
        if formset.is_valid():
            # Check if at least one item is filled
            has_items = any(formset.cleaned_data for form in formset if form.cleaned_data and not form.cleaned_data.get('DELETE', False))
            if not has_items:
                form.add_error(None, 'É necessário adicionar pelo menos um item à transação.')
                return self.form_invalid(form)
            
            # Save transaction and items
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.owner = self.request.user
                self.object.save()
                
                # Save formset
                formset.instance = self.object
                formset.save()
                
                # Calculate total amount
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
            context['formset'] = TransactionItemFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = TransactionItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        # Check if formset is valid
        if formset.is_valid():
            # Check if at least one item is filled
            has_items = any(formset.cleaned_data for form in formset if form.cleaned_data and not form.cleaned_data.get('DELETE', False))
            if not has_items:
                form.add_error(None, 'É necessário adicionar pelo menos um item à transação.')
                return self.form_invalid(form)
            
            # Save transaction and items
            with transaction.atomic():
                self.object = form.save()
                
                # Save formset
                formset.instance = self.object
                formset.save()
                
                # Calculate total amount
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
    # Get current month and year
    today = timezone.now().date()
    year = today.year
    month = today.month
    
    # Get summary data
    summary = get_month_summary(request.user, year, month)
    
    # Get category totals
    category_totals = get_category_totals(request.user, year, month)
    
    # Get daily balance series
    daily_balance = get_daily_balance_series(request.user, year, month)
    
    context = {
        'summary': summary,
        'category_totals': category_totals,
        'daily_balance': daily_balance,
        'month_name': calendar.month_name[month],
        'year': year,
    }
    
    return render(request, 'core/dashboard.html', context)