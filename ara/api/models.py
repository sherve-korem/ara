#  Copyright (c) 2018 Red Hat, Inc.
#
#  This file is part of ARA Records Ansible.
#
#  ARA is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ARA is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ARA.  If not, see <http://www.gnu.org/licenses/>.

from django.db import models
from django.utils import timezone


class Base(models.Model):
    """
    Abstract base model part of every model
    """

    class Meta:
        abstract = True

    id = models.BigAutoField(primary_key=True, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Duration(Base):
    """
    Abstract model for models with a concept of duration
    """

    class Meta:
        abstract = True

    started = models.DateTimeField(default=timezone.now)
    ended = models.DateTimeField(blank=True, null=True)


class FileContent(Base):
    """
    Contents of a uniquely stored and compressed file.
    Running the same playbook twice will yield two playbook files but just
    one file contents.
    """

    class Meta:
        db_table = 'file_contents'

    sha1 = models.CharField(max_length=40, unique=True)
    contents = models.BinaryField(max_length=(2 ** 32) - 1)

    def __str__(self):
        return '<FileContent %s:%s>' % (self.id, self.sha1)


class File(Base):
    """
    Data about Ansible files (playbooks, tasks, role files, var files, etc).
    Multiple files can reference the same FileContent record.
    """

    class Meta:
        db_table = 'files'

    path = models.CharField(max_length=255)
    content = models.ForeignKey(FileContent, on_delete=models.CASCADE, related_name='files')

    def __str__(self):
        return '<File %s:%s>' % (self.id, self.path)


class Label(Base):
    """
    A label is a generic container meant to group or correlate different
    playbooks. It could be a single playbook run. It could be a "group" of
    playbooks.
    It could represent phases or dynamic logical grouping and tagging of
    playbook runs.
    You could have a label named "failures" and make it so failed playbooks
    are added to this report, for example.
    The main purpose of this is to make the labels customizable by the user.
    """

    class Meta:
        db_table = 'labels'

    name = models.CharField(max_length=255)
    description = models.BinaryField(max_length=(2 ** 32) - 1)

    def __str__(self):
        return '<Label %s: %s>' % (self.id, self.name)


class Playbook(Duration):
    """
    An entry in the 'playbooks' table represents a single execution of the
    ansible or ansible-playbook commands. All the data for that execution
    is tied back to this one playbook.
    """

    class Meta:
        db_table = 'playbooks'

    ansible_version = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    parameters = models.BinaryField(max_length=(2 ** 32) - 1)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='playbooks')
    files = models.ManyToManyField(File)
    labels = models.ManyToManyField(Label)

    def __str__(self):
        return '<Playbook %s>' % self.id


class Record(Base):
    """
    A rudimentary key/value table to associate arbitrary data to a playbook.
    Used with the ara_record and ara_read Ansible modules.
    """

    class Meta:
        db_table = 'records'
        unique_together = ('key', 'playbook',)

    key = models.CharField(max_length=255)
    value = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=255)
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE, related_name='records')

    def __str__(self):
        return '<Record %s:%s>' % (self.id, self.key)


class Play(Duration):
    """
    Data about Ansible plays.
    Hosts, tasks and results are childrens of an Ansible play.
    """

    class Meta:
        db_table = 'plays'

    name = models.CharField(max_length=255, blank=True, null=True)
    completed = models.BooleanField(default=False)
    playbook = models.ForeignKey(Playbook, on_delete=models.CASCADE, related_name='plays')

    def __str__(self):
        return '<Play %s:%s>' % (self.id, self.name)


class Task(Duration):
    """Data about Ansible tasks."""

    class Meta:
        db_table = 'tasks'

    name = models.TextField(blank=True, null=True)
    action = models.TextField()
    lineno = models.IntegerField()
    tags = models.BinaryField(max_length=(2 ** 32) - 1)
    handler = models.BooleanField()
    completed = models.BooleanField(default=False)

    play = models.ForeignKey(Play, on_delete=models.CASCADE, related_name='tasks')
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='tasks')

    def __str__(self):
        return '<Task %s:%s>' % (self.name, self.id)


class Host(Base):
    """
    Data about Ansible hosts.
    Contains compressed host facts and statistics about the host for the
    playbook.
    """

    class Meta:
        db_table = 'hosts'
        unique_together = ('name', 'play',)

    name = models.CharField(max_length=255)
    facts = models.BinaryField(max_length=(2 ** 32) - 1)
    changed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    ok = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    unreachable = models.IntegerField(default=0)
    play = models.ForeignKey(Play, on_delete=models.DO_NOTHING, related_name='hosts')

    def __str__(self):
        return '<Host %s:%s>' % (self.id, self.name)


class Result(Duration):
    """
    Data about Ansible results.
    A task can have many results if the task is run on multiple hosts.
    """

    class Meta:
        db_table = 'results'

    # Ansible statuses
    OK = 'ok'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    UNREACHABLE = 'unreachable'
    # ARA specific statuses (derived or assumed)
    CHANGED = 'changed'
    IGNORED = 'ignored'
    UNKNOWN = 'unknown'

    STATUS = (
        (OK, 'ok'),
        (FAILED, 'failed'),
        (SKIPPED, 'skipped'),
        (UNREACHABLE, 'unreachable'),
        (CHANGED, 'changed'),
        (IGNORED, 'ignored'),
        (UNKNOWN, 'unknown')
    )

    status = models.CharField(max_length=25, choices=STATUS, default=UNKNOWN)
    # todo use a single Content table
    content = models.BinaryField(max_length=(2 ** 32) - 1)
    host = models.ForeignKey(Host, on_delete=models.CASCADE, related_name='results')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='results')

    def __str__(self):
        return '<Result %s, %s>' % (self.id, self.status)