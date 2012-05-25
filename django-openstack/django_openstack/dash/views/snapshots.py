# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2011 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Views for managing Nova instance snapshots.
"""

import datetime
import logging
import re

from django import http
from django import template
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render_to_response
from django.utils.translation import ugettext as _
from django import shortcuts

from django_openstack import api
from django_openstack import forms
from openstackx.api import exceptions as api_exceptions
from glance.common import exception as glance_exception
from django_openstack import utils

LOG = logging.getLogger('django_openstack.dash.views.snapshots')


class CreateSnapshot(forms.SelfHandlingForm):
    tenant_id = forms.CharField(widget=forms.HiddenInput())
    instance_id = forms.CharField(widget=forms.TextInput(
        attrs={'readonly': 'readonly'}))
    name = forms.CharField(max_length="20", label="Snapshot Name")

    def handle(self, request, data):
        try:
	    resources = utils.get_resources(request, request.user.tenant_id)
	    instance = api.server_get(request, data['instance_id'])
	    disk_gb = 0
	    all_images = []
	    all_images = api.image_list_detailed(request)
	    if not all_images:
 		messages.info(request, "There are currently no images.")
	    images = [im for im in all_images
              if im['container_format'] not in ['aki', 'ari']]
	    for image in images:
    		if int(image['id']) == int(instance.attrs.image_ref):
		    disk_gb = image['size'] / (1024 * 1024 * 1024)
	    if disk_gb > resources['free_disk']:
	        raise Exception('Not enough space to store the snapshot: image_size=%s free_disk=%s' % (disk_gb, resources['free_disk']))
            LOG.info('Creating snapshot "%s"' % data['name'])
            snapshot = api.snapshot_create(request,
                    data['instance_id'],
                    data['name'] + '.snap')
            instance = api.server_get(request, data['instance_id'])

            messages.info(request, 'Snapshot "%s" created for instance "%s"' %\
                                    (data['name'], instance.name))
            return shortcuts.redirect('dash_snapshots', data['tenant_id'])
        except glance_exception.ClientConnectionError, e:
            LOG.exception("Error connecting to glance")
            messages.error(request, "Error connecting to glance: %s" % str(e))
        except glance_exception.Error, e:
            LOG.exception("Error retrieving image list")
            messages.error(request, "Error retrieving image list: %s" % str(e))
        except api_exceptions.ApiException, e:
            msg = 'Error Creating Snapshot: %s' % e.message
            LOG.exception(msg)
            messages.error(request, msg)
            return shortcuts.redirect(request.build_absolute_uri())

class DeleteImage(forms.SelfHandlingForm):
    image_id = forms.CharField(required=True)

    def handle(self, request, data):
        image_id = data['image_id']
        tenant_id = request.user.tenant_id
        try:
            image = api.image_get(request, image_id)
            if image.owner == request.user.tenant_id:
                api.image_delete(request, image_id)
            else:
                messages.info(request, "Unable to delete image, you are not \
                                       its owner.")
                return redirect('dash_images_update', tenant_id, image_id)
        except glance_exception.ClientConnectionError, e:
            LOG.exception("Error connecting to glance")
            messages.error(request, "Error connecting to glance: %s"
                                    % e.message)
        except glance_exception.Error, e:
            LOG.exception('Error deleting image with id "%s"' % image_id)
            messages.error(request, "Error deleting image: %s: %s"
                                    % (image_id, e.message))
        return redirect(request.build_absolute_uri())

@login_required
def index(request, tenant_id):
    for f in (DeleteImage, ):
        unused, handled = f.maybe_handle(request)
        if handled:
            return handled
    delete_form = DeleteImage()
    images = []

    try:
        images = api.snapshot_list_detailed(request)
    except glance_exception.ClientConnectionError, e:
        msg = 'Error connecting to glance: %s' % str(e)
        LOG.exception(msg)
        messages.error(request, msg)
    except glance_exception.Error, e:
        msg = 'Error retrieving image list: %s' % str(e)
        LOG.exception(msg)
        messages.error(request, msg)

    return render_to_response(
    'django_openstack/dash/snapshots/index.html', {
        'delete_form': delete_form,
        'images': images,
    }, context_instance=template.RequestContext(request))


@login_required
def create(request, tenant_id, instance_id):
    form, handled = CreateSnapshot.maybe_handle(request,
                        initial={'tenant_id': tenant_id,
                                 'instance_id': instance_id})
    if handled:
        return handled

    try:
        instance = api.server_get(request, instance_id)
    except api_exceptions.ApiException, e:
        msg = "Unable to retreive instance: %s" % str(e)
        LOG.exception(msg)
        messages.error(request, msg)
        return shortcuts.redirect('dash_instances', tenant_id)

    valid_states = ['ACTIVE']
    if instance.status not in valid_states:
        messages.error(request, "To snapshot, instance state must be\
                                  one of the following: %s" %
                                  ', '.join(valid_states))
        return shortcuts.redirect('dash_instances', tenant_id)

    return shortcuts.render_to_response(
    'django_openstack/dash/snapshots/create.html', {
        'instance': instance,
        'create_form': form,
    }, context_instance=template.RequestContext(request))
