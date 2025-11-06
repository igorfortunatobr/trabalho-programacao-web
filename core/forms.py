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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Garantir que a data seja renderizada no formato correto
        if self.instance and self.instance.pk and hasattr(self.instance, 'date'):
            # Formatar a data no formato YYYY-MM-DD esperado pelo input date
            if self.instance.date:
                self.fields['date'].widget.format = '%Y-%m-%d'
                self.fields['date'].initial = self.instance.date.strftime('%Y-%m-%d')

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

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise forms.ValidationError("O valor deve ser maior ou igual a 0,01.")
        return amount


# Cria o formset inline para TransactionItem
TransactionItemFormSet = inlineformset_factory(
    Transaction, 
    TransactionItem, 
    form=TransactionItemForm,
    extra=1,
    can_delete=True
)