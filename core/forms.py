from django import forms
from django.forms import inlineformset_factory
from .models import Transaction, TransactionItem, Category
from decimal import Decimal
from django.utils import timezone


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['description', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise forms.ValidationError("A data não pode ser no futuro.")
        return date


class TransactionItemForm(forms.ModelForm):
    class Meta:
        model = TransactionItem
        fields = ['category', 'amount']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise forms.ValidationError("O valor deve ser maior ou igual a 0,01.")
        return amount


# Create the inline formset for TransactionItem
TransactionItemFormSet = inlineformset_factory(
    Transaction, 
    TransactionItem, 
    form=TransactionItemForm,
    extra=1,
    can_delete=True
)