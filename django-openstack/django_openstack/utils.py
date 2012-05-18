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

import datetime
from django.conf import settings


def time():
    '''Overrideable version of datetime.datetime.today'''
    if time.override_time:
        return time.override_time
    return datetime.time()

time.override_time = None


def today():
    '''Overridable version of datetime.datetime.today'''
    if today.override_time:
        return today.override_time
    return datetime.datetime.today()

today.override_time = None


def utcnow():
    '''Overridable version of datetime.datetime.utcnow'''
    if utcnow.override_time:
        return utcnow.override_time
    return datetime.datetime.utcnow()

utcnow.override_time = None

def get_resources(request, tenant):
    from django_openstack import api
    from os import statvfs
    resources = {}
    now =utcnow()
    usage = api.usage_get(request, tenant, now, now)
    try:
        resources['active_disk'] = usage.total_active_disk_size
    except:
        resources['active_disk'] = 0
    resources['active_disk'] += sum( [v.size for v in api.volume_list(request)] )
    resources['active_disk'] += sum( [i.size/1073741824.0 for i in api.image_list_detailed(request)] )
    fs = statvfs(settings.SHARED_FOLDER)
    resources['total_disk'] = fs.f_blocks*fs.f_bsize / 1073741824.0
    resources['free_disk'] = resources['total_disk'] - resources['active_disk']
    try:
        resources['active_vcpus'] = usage.total_active_vcpus
    except:
        resources['active_vcpus'] = 0
    quota = api.tenant_quota_get(request, tenant)
    resources['total_vcpus'] = quota.cores
    resources['free_vcpus'] = resources['total_vcpus'] - resources['active_vcpus']
    instances = api.server_list(request)
    resources['active_memory'] = sum([i.attrs.memory_mb for i in instances])
    return resources