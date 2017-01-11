from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.reverse import reverse
from django.utils.translation import ugettext_lazy as _
from datetime import date

from .models import Sprint, Task


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):

    full_name = serializers.CharField(source='get_full_name', read_only=True)
    links = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', User.USERNAME_FIELD, 'full_name', 'is_active', 'links')

    def get_links(self, obj):
        request = self.context['request']
        username = obj.get_username()
        return {
            'self': reverse('user-detail',
                            kwargs={User.USERNAME_FIELD: username}, request=request),
            'tasks': '{}?assigned={}'.format(
                reverse('task-list', request=request), username)
        }


class SprintSerializer(serializers.ModelSerializer):

    links = serializers.SerializerMethodField()

    class Meta:
        model = Sprint
        fields = ('id', 'name', 'description', 'end', 'links')

    def get_links(self, obj):
        request = self.context['request']
        return {
            'self': reverse('sprint-detail',
                            kwargs={'pk': obj.pk}, request=request),
            'tasks': reverse('task-list',
                             request=request) + "?sprint={}".format(obj.pk),
            'channel': '{proto}://{server}/{channel}'.format(
                proto='wss' if settings.WATERCOOLER_SECURE else 'ws',
                server = settings.WATERCOOLER_SERVER,
                channel = obj.pk
            ),
        }

    def validate_end(self, value):
        end_date = value
        new = not self.instance
        changed = self.instance and self.instance.end != end_date
        if (new or changed) and (end_date < date.today()):
            msg = _('End date connot be in the past')
            raise serializers.ValidationError(msg)
        return value

class TaskSerializer(serializers.ModelSerializer):

    assigned = serializers.SlugRelatedField(
        slug_field=User.USERNAME_FIELD, required=False, queryset = User.objects.all()
    )

    status_display = serializers.SerializerMethodField()
    links = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ('id', 'name', 'description', 'sprint', 'status', 'order',
                  'assigned', 'started', 'due', 'completed', 'links', 'status_display' )

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_links(self, obj):
        request = self.context['request']
        links = {
            'self': reverse('task-detail',
                            kwargs={'pk':obj.pk}, request=request),
            'sprint': None,
            'assigned': None,
        }

        if obj.sprint_id:
            links['sprint'] = reverse('sprint-detail',
                                      kwargs={'pk':obj.sprint_id}, request=request)

        if obj.assigned:
            links['assigned'] = reverse('user-detail',
                                      kwargs={User.USERNAME_FIELD:obj.assigned}, request=request)

        return links

    def validate_sprint(self, value):
        sprint = value
        if self.instance and self.instance.pk:
            if sprint != self.instance.sprint:
                if self.instance.status == Task.STATUS_DONE:
                    msg = _("Cannot change the sprint of completed Task")
                    raise serializers.ValidationError(msg)
                if sprint and sprint.end < date.today():
                    msg = _("Cannot assign Task to past Sprints")
                    raise serializers.ValidationError(msg)
            else:
                if sprint and sprint.end < date.today():
                    msg = _("Cannot assign Task to past Sprints")
                    raise serializers.ValidationError(msg)

        return value

    def validate(self, attrs):
        sprint = attrs.get('sprint')
        status = attrs.get('status', Task.STATUS_TODO)
        started = attrs.get('started')
        completed = attrs.get('completed')
        if not sprint and status != Task.STATUS_TODO:
            msg = _("Backlog tasks must have not started status")
            raise serializers.ValidationError(msg)
        if started and status == Task.STATUS_TODO:
            msg = _("Start date can't be set for Not Started Tak")
            raise serializers.ValidationError(msg)
        if completed and status != Task.STATUS_DONE:
            msg = _("Completed Date can't be set of incomplete task")
            raise serializers.ValidationError(msg)
        return attrs