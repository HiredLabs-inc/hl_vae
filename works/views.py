from django.shortcuts import render


# Create your views here.
def home_view(request):
    return render(request, "index.html")


def about_view(request):
    return render(request, "about.html")


def works_view(request):
    # db logic to get all approved works
    # approved_works = SQL command-- FROM SELECT WHERE
    approved_works = [1, 2, 3]
    context = {"work_number_1": approved_works}
    return render(request, "works.html", context)


def submit_a_work_view(request):
    return render(request, "submit_a_work.html")


def reviewer_view(request):
    return render(request, "reviewer.html")
