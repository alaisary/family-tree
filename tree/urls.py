from django.urls import path
from . import views

urlpatterns = [
    # Health check
    path('healthz/', views.healthz, name='healthz'),

    # Tree
    path('', views.tree_view, name='tree_view'),
    path('api/tree/', views.tree_data, name='tree_data'),

    # Search
    path('api/search/', views.search_persons, name='search_persons'),

    # Relationship Finder
    path('api/relationship/', views.find_relationship, name='find_relationship'),

    # Person
    path('api/person/<int:person_id>/', views.person_detail, name='person_detail'),
    path('api/person/<int:person_id>/edit-form/', views.person_edit_form, name='person_edit_form'),
    path('api/person/<int:person_id>/update/', views.person_update, name='person_update'),
    path('api/person/<int:person_id>/add-child/', views.add_child, name='add_child'),
    path('api/person/<int:person_id>/set-mother/', views.set_mother, name='set_mother'),
    path('api/person/<int:person_id>/edit-log/', views.person_edit_log, name='person_edit_log'),
    path('api/person/<int:person_id>/delete/', views.delete_person, name='delete_person'),
    path('api/person/<int:person_id>/move/', views.move_person, name='move_person'),
    path('api/person/<int:person_id>/delete-photo/', views.delete_photo, name='delete_photo'),

    # Root (first person)
    path('api/root/add/', views.add_root, name='add_root'),

    # Stats & Export
    path('api/branch-stats/<int:person_id>/', views.branch_stats, name='branch_stats'),
    path('api/branch-tree/<int:person_id>/', views.branch_tree, name='branch_tree'),
    path('api/stats/', views.tree_stats, name='tree_stats'),
    path('api/export/csv/', views.export_csv, name='export_csv'),
]
