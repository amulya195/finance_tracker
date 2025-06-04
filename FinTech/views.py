from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.contrib.auth.models import User, auth 
from datetime import date, datetime, timedelta
from django.db.models import Sum
from .models import Expense, Income, IncomeCategory, ExpenseCategory, Account, Budget
import csv
import logging

logger = logging.getLogger(__name__)

# Helper function to get past 10 days' income/expense data
def get_last_10_days_data(model, user):
    data = []
    for i in range(10):
        day_total = model.objects.filter(
            user=user,
            date__gte=date.today() - timedelta(days=i),
            date__lt=date.today() - timedelta(days=i - 1)
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        data.append(day_total)
    data.reverse()
    return data

# Dashboard
def dashboard(request):
    if request.user.is_authenticated:
        my_account = Account.objects.get(user=request.user)
        balance = my_account.balance

        # Expenses By Category
        out_dict = {catg.name: 0 for catg in ExpenseCategory.objects.filter(user=request.user)}
        for expense in Expense.objects.filter(user=request.user):
            out_dict[expense.category.name] += expense.amount

        catg_list, catg_total_list = zip(*out_dict.items()) if out_dict else ([], [])

        # Last 10 days income and expense data
        Income_last_10days_amount = get_last_10_days_data(Income, request.user)
        Expense_last_10days_amount = get_last_10_days_data(Expense, request.user)

        # Last 10 day labels
        month_map = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                     "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"]
        pre_10days_list = [
            f"{(datetime.now().date() - timedelta(days=i)).day}{month_map[(datetime.now().date() - timedelta(days=i)).month - 1]}"
            for i in range(10)
        ][::-1]

        return render(request, "dashboard.html", {
            "balance": balance,
            "category_list": catg_list,
            "catg_total_list": catg_total_list,
            "pre_10days_list": pre_10days_list,
            "Income_last_10days_amount": Income_last_10days_amount,
            "Expense_last_10days_amount": Expense_last_10days_amount
        })
    return redirect("/")

# Income
def income(request):
    if request.user.is_authenticated:
        if request.method == "POST":
            name = request.POST['name']
            category_id = request.POST.get('category')
            amount = float(request.POST['amount'])
            date_val = request.POST['date']
            note = request.POST.get('note')
            category = get_object_or_404(IncomeCategory, user=request.user, id=category_id)

            my_account = Account.objects.get(user=request.user)
            my_account.balance += amount
            my_account.save()

            Income.objects.create(name=name, user=request.user, category=category, amount=amount, date=date_val, note=note)
            logger.info("Income added and account updated.")
            return redirect('/incomes')

        incomes_catg = IncomeCategory.objects.filter(user=request.user)
        incomes = Income.objects.filter(user=request.user)
        return render(request, "income.html", {"categories": incomes_catg, "incomes": incomes})
    return redirect("/")

# Expenses
def expenses(request):
    if request.user.is_authenticated:
        if request.method == "POST":
            name = request.POST['name']
            category_id = request.POST.get('category')
            amount = float(request.POST['amount'])
            date_val = request.POST['date']
            note = request.POST.get('note')
            category = get_object_or_404(ExpenseCategory, user=request.user, id=category_id)

            my_account = Account.objects.get(user=request.user)
            my_account.balance -= amount
            my_account.save()

            Expense.objects.create(name=name, user=request.user, category=category, amount=amount, date=date_val, note=note)
            logger.info("Expense added and account updated.")
            return redirect('/expenses')

        expenses_catg = ExpenseCategory.objects.filter(user=request.user)
        expenses = Expense.objects.filter(user=request.user)
        return render(request, "expense.html", {"categories": expenses_catg, "expenses": expenses})
    return redirect("/")

# Edit Income
def edit_income(request, id):
    if request.user.is_authenticated:
        income = get_object_or_404(Income, id=id, user=request.user)
        if request.method == "POST":
            new_amount = float(request.POST['amount'])
            diff = new_amount - income.amount
            income.name = request.POST['name']
            income.amount = new_amount
            income.date = request.POST['date']
            income.note = request.POST.get('note')
            income.category = get_object_or_404(IncomeCategory, user=request.user, id=request.POST.get('category'))
            income.save()

            my_account = Account.objects.get(user=request.user)
            my_account.balance += diff
            my_account.save()
            return redirect("/incomes")

        categories = IncomeCategory.objects.filter(user=request.user)
        return render(request, "income_edit.html", {"income": income, "categories": categories})
    return redirect("/")

# Edit Expense
def edit_expense(request, id):
    if request.user.is_authenticated:
        expense = get_object_or_404(Expense, id=id, user=request.user)
        if request.method == "POST":
            new_amount = float(request.POST['amount'])
            diff = new_amount - expense.amount
            expense.name = request.POST['name']
            expense.amount = new_amount
            expense.date = request.POST['date']
            expense.note = request.POST.get('note')
            expense.category = get_object_or_404(ExpenseCategory, user=request.user, id=request.POST.get('category'))
            expense.save()

            my_account = Account.objects.get(user=request.user)
            my_account.balance -= diff
            my_account.save()
            return redirect("/expenses")

        categories = ExpenseCategory.objects.filter(user=request.user)
        return render(request, "expense_edit.html", {"expense": expense, "categories": categories})
    return redirect("/")

# Delete Expense
def delete_expense(request, id):
    if request.user.is_authenticated:
        expense = get_object_or_404(Expense, id=id, user=request.user)
        Account.objects.filter(user=request.user).update(balance=F('balance') + expense.amount)
        expense.delete()
        return redirect("/expenses")
    return redirect("/")

# Delete Income
def delete_income(request, id):
    if request.user.is_authenticated:
        income = get_object_or_404(Income, id=id, user=request.user)
        Account.objects.filter(user=request.user).update(balance=F('balance') - income.amount)
        income.delete()
        return redirect("/incomes")
    return redirect("/")

# Expense Report
def expense_report(request, duration):
    if not request.user.is_authenticated:
        return redirect("/")
    duration_map = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30)
    }
    date_filter = datetime.now() - duration_map.get(duration, timedelta(days=0))
    expenses = Expense.objects.filter(user=request.user, date__gte=date_filter).order_by("date") if duration in duration_map else Expense.objects.filter(user=request.user).order_by("date")

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Expenses_{duration}_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Sr.No.", "Name", "Category", "Amount", "Date", "Note"])
    for idx, e in enumerate(expenses, 1):
        writer.writerow([idx, e.name, e.category, e.amount, e.date, e.note])
    return response

# Income Report
def income_report(request, duration):
    if not request.user.is_authenticated:
        return redirect("/")
    duration_map = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=30)
    }
    date_filter = datetime.now() - duration_map.get(duration, timedelta(days=0))
    incomes = Income.objects.filter(user=request.user, date__gte=date_filter).order_by("date") if duration in duration_map else Income.objects.filter(user=request.user).order_by("date")

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Incomes_{duration}_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Sr.No.", "Name", "Category", "Amount", "Date", "Note"])
    for idx, i in enumerate(incomes, 1):
        writer.writerow([idx, i.name, i.category, i.amount, i.date, i.note])
    return response

# Settings Page
def settings(request):
    if request.user.is_authenticated:
        profile = request.user
        expense_categories = ExpenseCategory.objects.filter(user=profile)
        income_categories = IncomeCategory.objects.filter(user=profile)
        if request.method == "POST":
            profile.first_name = request.POST['first_name']
            profile.last_name = request.POST['last_name']
            profile.email = request.POST['email']
            profile.save()
            return redirect("/profile")
        return render(request, "settings.html", {"profile": profile, "expense_categories": expense_categories, "income_categories": income_categories})
    return redirect("/")

# Category Add/Remove
def add_income_category(request):
    if request.user.is_authenticated and request.method == "POST":
        IncomeCategory.objects.create(user=request.user, name=request.POST['name'])
    return redirect("/settings")

def add_expense_category(request):
    if request.user.is_authenticated and request.method == "POST":
        ExpenseCategory.objects.create(user=request.user, name=request.POST['name'])
    return redirect("/settings")

def remove_expense_category(request, id):
    if request.user.is_authenticated:
        get_object_or_404(ExpenseCategory, user=request.user, id=id).delete()
    return redirect("/settings")

def remove_income_category(request, id):
    if request.user.is_authenticated:
        get_object_or_404(IncomeCategory, user=request.user, id=id).delete()
    return redirect("/settings")

# Index
def index(request):
    return redirect("/dashboard") if request.user.is_authenticated else render(request, "index.html")

# Signup
def signup(request):
    if request.method == "POST":
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        email = request.POST['email']
        password = request.POST['password']
        if User.objects.filter(username=email).exists():
            return redirect('/')
        user = User.objects.create_user(username=email, email=email, password=password, first_name=first_name, last_name=last_name)
        Account.objects.create(user=user, balance=0, details=f"Primary account for User={user.id}", name=f"Account for {user.id}-{first_name}")
        return redirect('/')
    return render(request, "index.html")

# Profile
def profile(request):
    if request.user.is_authenticated:
        account = Account.objects.get(user=request.user)
        if request.method == "POST":
            request.user.first_name = request.POST['first_name']
            request.user.last_name = request.POST['last_name']
            request.user.email = request.POST['email']
            request.user.save()
            return redirect("/profile")
        return render(request, "profile.html", {"profile": request.user, "balance": account.balance})
    return redirect("/")

# Login
def login(request):
    if request.method == "POST":
        user = auth.authenticate(username=request.POST['email'], password=request.POST['password'])
        if user:
            auth.login(request, user)
            return redirect("/dashboard")
        return redirect("/")
    return render(request, "index.html")

def logout(request):
    if request.user.is_authenticated:
        auth.logout(request)
    return redirect("/")
