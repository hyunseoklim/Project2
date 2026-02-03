from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Business


@login_required
def business_list(request):
    businesses = Business.active.filter(user=request.user)

    # 필터링
    branch_type = request.GET.get('branch_type')
    if branch_type:
        businesses = businesses.filter(branch_type=branch_type)

    context = {
        'businesses': businesses,
        'selected_branch_type': branch_type,
    }
    return render(request, 'businesses/business_list.html', context)


@login_required
def business_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location', '')
        business_type = request.POST.get('business_type', '')
        registration_number = request.POST.get('registration_number', '')

        Business.objects.create(
            user=request.user,
            name=name,
            location=location,
            business_type=business_type,
            registration_number=registration_number,
        )
        messages.success(request, f"'{name}' 사업장이 생성되었습니다.")
        return redirect('businesses:business_list')

    return render(request, 'businesses/business_form.html')


@login_required
def business_detail(request, pk):
    business = get_object_or_404(Business, pk=pk, user=request.user, is_active=True)
    return render(request, 'businesses/business_detail.html', {'business': business})


@login_required
def business_update(request, pk):
    business = get_object_or_404(Business, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        business.name = request.POST.get('name', business.name)
        business.location = request.POST.get('location', business.location)
        business.business_type = request.POST.get('business_type', business.business_type)
        business.registration_number = request.POST.get('registration_number', business.registration_number)
        business.save()
        messages.success(request, f"'{business.name}' 사업장이 수정되었습니다.")
        return redirect('businesses:business_detail', pk=business.pk)

    return render(request, 'businesses/business_form.html', {'business': business})


@login_required
def business_delete(request, pk):
    business = get_object_or_404(Business, pk=pk, user=request.user, is_active=True)

    if request.method == 'POST':
        business.soft_delete()
        messages.success(request, f"'{business.name}' 사업장이 삭제되었습니다.")
        return redirect('businesses:business_list')

    return render(request, 'businesses/business_confirm_delete.html', {'business': business})