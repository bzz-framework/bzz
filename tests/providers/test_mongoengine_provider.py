#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import locale

import mongoengine
import cow.server as server
import cow.plugins.mongoengine_plugin as mongoengine_plugin
import tornado.testing as testing
from tornado.httpclient import HTTPError
from preggy import expect
import derpconf.config as config
import bson.objectid as oid

import bzz
import bzz.providers.mongoengine_provider as me
import bzz.signals as signals
import bzz.utils as utils
import tests.base as base
import tests.models.mongoengine_models as models
import tests.fixtures as fix


def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


class TestServer(server.Server):
    def get_plugins(self):
        return [
            mongoengine_plugin.MongoEnginePlugin
        ]

    def get_handlers(self):
        routes = [
            bzz.ModelHive.routes_for('mongoengine', models.User),
            bzz.ModelHive.routes_for('mongoengine', models.OtherUser),
            bzz.ModelHive.routes_for('mongoengine', models.Parent),
            bzz.ModelHive.routes_for('mongoengine', models.Parent2),
            bzz.ModelHive.routes_for('mongoengine', models.Team),
            bzz.ModelHive.routes_for('mongoengine', models.Student),
            bzz.ModelHive.routes_for('mongoengine', models.CustomQuerySet),
            bzz.ModelHive.routes_for('mongoengine', models.UniqueUser),
            bzz.ModelHive.routes_for('mongoengine', models.ValidationUser),
        ]
        return bzz.flatten(routes)


class MongoEngineProviderTestCase(base.ApiTestCase):
    def setUp(self):
        super(MongoEngineProviderTestCase, self).setUp()
        signals.pre_get_instance.receivers = {}
        signals.post_get_instance.receivers = {}
        signals.pre_get_list.receivers = {}
        signals.post_get_list.receivers = {}
        signals.pre_create_instance.receivers = {}
        signals.post_create_instance.receivers = {}
        signals.pre_update_instance.receivers = {}
        signals.post_update_instance.receivers = {}
        signals.pre_delete_instance.receivers = {}
        signals.post_delete_instance.receivers = {}

        models.User.objects.delete()
        models.OtherUser.objects.delete()
        models.Parent.objects.delete()
        models.Parent2.objects.delete()
        models.Team.objects.delete()
        models.Student.objects.delete()

    def get_config(self):
        return dict(
            MONGO_DATABASES={
                'default': {
                    'host': 'localhost',
                    'port': 3334,
                    'database': 'bzz_test'
                }
            },
        )

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    @testing.gen_test
    def test_can_create_user(self):
        response = yield self.http_client.fetch(
            self.get_url('/user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers).to_include('location')

        expected_url = '/user/%s/' % response.headers['X-Created-Id']
        expect(response.headers['location']).to_equal(expected_url)

    @testing.gen_test
    def test_can_get_user(self):
        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj['email']).to_equal(user.email)
        expect(obj['name']).to_equal(user.name)
        expect(obj['slug']).to_equal(user.slug)

    @testing.gen_test
    def test_getting_invalid_user_fails_with_403(self):
        objectid = oid.ObjectId()
        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/user/%s' % objectid)
            )
        expect(err.error.code).to_equal(404)

    @testing.gen_test
    def test_can_create_other_user(self):
        response = yield self.http_client.fetch(
            self.get_url('/other_user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers['X-Created-Id']).to_equal('bernardo-heynemann')
        expect(response.headers).to_include('location')

        expected_url = '/other_user/%s/' % response.headers['X-Created-Id']
        expect(response.headers['location']).to_equal(expected_url)

    @testing.gen_test
    def test_can_get_other_user(self):
        user = fix.OtherUserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/other_user/%s' % user.slug),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj['user']).to_equal('%s <%s>' % (user.name, user.email))

    @testing.gen_test
    def test_can_get_list(self):
        models.User.objects.delete()
        for i in range(30):
            fix.UserFactory.create()

        response = yield self.http_client.fetch(
            self.get_url('/user/'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(20)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=2'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(10)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=3'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(10)

        response = yield self.http_client.fetch(
            self.get_url('/user/?page=qwe'),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(20)

    @testing.gen_test
    def test_can_get_filtered_list(self):
        models.User.objects.delete()
        users = []
        for i in range(30):
            users.append(fix.UserFactory.create())

        response = yield self.http_client.fetch(
            self.get_url('/user/?slug=%s' % users[0].slug),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(1)

    @testing.gen_test
    def test_can_update(self):
        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='PUT',
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body='name=Rafael%20Floriano&email=rflorianobr@gmail.com'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        loaded_user = models.User.objects.get(id=user.id)
        expect(loaded_user.name).to_equal('Rafael Floriano')
        expect(loaded_user.slug).to_equal('rafael-floriano')
        expect(loaded_user.email).to_equal('rflorianobr@gmail.com')

    @testing.gen_test
    def test_can_delete(self):
        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        with expect.error_to_happen(mongoengine.errors.DoesNotExist):
            models.User.objects.get(id=user.id)

    @testing.gen_test
    def test_can_delete_not_found_instance(self):
        response = yield self.http_client.fetch(
            self.get_url('/other_user/invalid'),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('FAIL')

    @testing.gen_test
    def test_can_subscribe_to_pre_create_signal(self):
        instances = []

        def handle_pre_create(sender, arguments, handler):
            instances.append((arguments, handler))

        signals.pre_create_instance.connect(handle_pre_create)

        response = yield self.http_client.fetch(
            self.get_url('/user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances[0][0]).to_be_like(['user'])

    @testing.gen_test
    def test_can_subscribe_to_pre_create_signal_on_internal_urls(self):
        instances = []

        def handle_pre_create(sender, arguments, handler):
            instances.append((sender, arguments, handler))

        signals.pre_create_instance.connect(handle_pre_create)

        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/' % team.id),
            method='POST',
            body='users[]=%s' % user.id
        )

        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances[0][0]).to_equal(models.User)
        expect(instances[0][1]).to_be_like(['team/%s' % team.id, 'users'])

    @testing.gen_test
    def test_can_subscribe_to_post_create_signal(self):
        instances = {}

        def handle_post_create(sender, instance, handler):
            instances[instance.slug] = instance

        signals.post_create_instance.connect(handle_post_create)

        response = yield self.http_client.fetch(
            self.get_url('/user/'),
            method='POST',
            body='name=Bernardo%20Heynemann&email=heynemann@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(instances).to_include('bernardo-heynemann')

    @testing.gen_test
    def test_can_subscribe_to_post_create_signal_on_internal_urls(self):
        instances = {}

        def handle_post_create(sender, instance, handler):
            instances[instance.slug] = (sender, instance)

        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()

        team = models.Team(name="test-team", users=[user])
        team.save()

        signals.post_create_instance.connect(handle_post_create)

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/' % team.id),
            method='POST',
            body='users[]=%s' % user.id
        )

        expect(response.code).to_equal(200)
        expect(instances).to_include('bernardo-heynemann')
        expect(instances['bernardo-heynemann'][0]).to_equal(models.User)

    @testing.gen_test
    def test_can_subscribe_to_pre_update_signal(self):
        instances = []

        def handle_pre_update(sender, arguments, handler):
            instances.append((arguments, handler))

        signals.pre_update_instance.connect(handle_pre_update)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='PUT',
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body='name=Rafael%20Floriano&email=rflorianobr@gmail.com'
        )

        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances[0][0]).to_be_like(['user/%s' % user.id])

    @testing.gen_test
    def test_can_subscribe_to_post_update_signal(self):
        instances = {}
        updated = {}

        def handle_post_update(sender, instance, updated_fields, handler):
            instances[instance.slug] = instance
            updated[instance.slug] = updated_fields

        signals.post_update_instance.connect(handle_post_update)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='PUT',
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body='name=Rafael%20Floriano&email=rflorianobr@gmail.com'
        )
        expect(response.code).to_equal(200)

        expect(instances).to_include('rafael-floriano')
        expect(updated).to_include('rafael-floriano')
        expect(updated['rafael-floriano']).to_be_like({
            'name': {
                'from': user.name,
                'to': 'Rafael Floriano'
            },
            'email': {
                'from': user.email,
                'to': 'rflorianobr@gmail.com'
            }
        })

    @testing.gen_test
    def test_can_subscribe_to_pre_delete_signal(self):
        instances = []

        def handle_pre_delete(sender, arguments, handler):
            instances.append((arguments, handler))

        signals.pre_delete_instance.connect(handle_pre_delete)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances[0][0]).to_be_like(['user/%s' % user.id])

    @testing.gen_test
    def test_can_subscribe_to_post_delete_signal(self):
        instances = {}

        def handle_post_delete(sender, instance, handler):
            instances[instance.slug] = instance

        signals.post_delete_instance.connect(handle_post_delete)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(instances).to_include(user.slug)

    @testing.gen_test
    def test_can_subscribe_to_pre_get_instance_signal(self):
        instances = []

        def handle_pre_get_instance(sender, arguments, handler):
            instances.append((sender, arguments, handler))

        signals.pre_get_instance.connect(handle_pre_get_instance)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
        )
        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances[0][0]).to_equal(models.User)
        expect(instances[0][1]).to_be_like(['user/%s' % user.id])

    @testing.gen_test
    def test_can_subscribe_to_pre_get_instance_signal_for_internal_classes(self):
        instances = []

        def handle_pre_get_instance(sender, arguments, handler):
            instances.append((sender, arguments, handler))

        signals.pre_get_instance.connect(handle_pre_get_instance)

        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/%s' % (str(team.id), str(user.id))),
        )

        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances[0][0]).to_equal(models.User)
        expect(instances[0][1]).to_be_like(['team/%s' % team.id, 'users/%s' % user.id])

    @testing.gen_test
    def test_can_subscribe_to_post_get_instance_signal(self):
        instances = {}

        def handle_post_get_instance(sender, instance, handler):
            instances[instance.slug] = instance

        signals.post_get_instance.connect(handle_post_get_instance)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user/%s' % user.id),
        )
        expect(response.code).to_equal(200)
        expect(instances).to_include(user.slug)

    @testing.gen_test
    def test_can_subscribe_to_post_get_instance_signal_for_internal_urls(self):
        instances = {}

        def handle_post_get_instance(sender, instance, handler):
            instances[instance.slug] = (sender, instance)

        signals.post_get_instance.connect(handle_post_get_instance)

        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/%s' % (str(team.id), str(user.id))),
        )
        expect(response.code).to_equal(200)
        expect(instances).to_length(1)
        expect(instances).to_include(user.slug)
        expect(instances[user.slug][0]).to_equal(models.User)
        expect(instances[user.slug][1].id).to_equal(user.id)

    @testing.gen_test
    def test_can_subscribe_to_pre_get_list_signal(self):
        lists = []

        def handle_pre_get_list(sender, arguments, handler):
            lists.append((arguments, handler))

        signals.pre_get_list.connect(handle_pre_get_list)

        fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user'),
        )
        expect(response.code).to_equal(200)
        expect(lists).to_length(1)
        expect(lists[0][0]).to_be_like(['user'])

    @testing.gen_test
    def test_can_subscribe_to_pre_get_list_signal_for_internal_classes(self):
        lists = []

        def handle_pre_get_list(sender, arguments, handler):
            lists.append((sender, arguments, handler))

        signals.pre_get_list.connect(handle_pre_get_list)

        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users' % str(team.id)),
        )

        expect(response.code).to_equal(200)
        expect(lists).to_length(1)
        expect(lists[0][0]).to_equal(models.User)
        expect(lists[0][1]).to_be_like(['team/%s' % team.id, 'users'])

    @testing.gen_test
    def test_can_subscribe_to_post_get_list_signal(self):
        lists = []

        def handle_post_get_list(sender, items, handler):
            lists.append(items)

        signals.post_get_list.connect(handle_post_get_list)

        user = fix.UserFactory.create()
        response = yield self.http_client.fetch(
            self.get_url('/user'),
        )
        expect(response.code).to_equal(200)
        expect(lists).to_length(1)
        expect(lists[0]).to_length(1)
        expect(lists[0][0].slug).to_equal(user.slug)

    @testing.gen_test
    def test_can_subscribe_to_post_get_list_signal_for_internal_urls(self):
        lists = []

        def handle_post_get_list(sender, items, handler):
            lists.append((sender, items))

        signals.post_get_list.connect(handle_post_get_list)

        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users' % str(team.id)),
        )

        expect(response.code).to_equal(200)
        expect(lists).to_length(1)
        expect(lists[0][0]).to_equal(models.User)
        expect(lists[0][1]).to_length(1)
        expect(lists[0][1][0].slug).to_equal(user.slug)

    @testing.gen_test
    def test_can_save_parent_with_child(self):
        response = yield self.http_client.fetch(
            self.get_url('/parent/'),
            method='POST',
            body='name=Bernardo%20Heynemann&child.first_name=Rodrigo&child.last_name=Lucena'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers).to_include('location')

        parent = models.Parent.objects.get(id=response.headers['X-Created-Id'])
        expect(parent.name).to_equal('Bernardo Heynemann')
        expect(parent.child).not_to_be_null()
        expect(parent.child.first_name).to_equal('Rodrigo')
        expect(parent.child.last_name).to_equal('Lucena')

    @testing.gen_test
    def test_can_save_parent_with_grandchild(self):
        response = yield self.http_client.fetch(
            self.get_url('/parent/'),
            method='POST',
            body='name=Bernardo%20Heynemann'
            '&child.first_name=Rodrigo'
            '&child.last_name=Lucena'
            '&child.child.first_name=Polo'
            '&child.child.last_name=Norte'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        expect(response.headers).to_include('location')

        parent = models.Parent.objects.get(id=response.headers['X-Created-Id'])
        expect(parent.name).to_equal('Bernardo Heynemann')

        expect(parent.child).not_to_be_null()
        expect(parent.child.first_name).to_equal('Rodrigo')
        expect(parent.child.last_name).to_equal('Lucena')

        expect(parent.child.child).not_to_be_null()
        expect(parent.child.child.first_name).to_equal('Polo')
        expect(parent.child.child.last_name).to_equal('Norte')

    @testing.gen_test
    def test_can_update_grandchild(self):
        parent = models.Parent.objects.create(name="test-user")

        response = yield self.http_client.fetch(
            self.get_url('/parent/%s/' % str(parent.id)),
            method='PUT',
            body='child.first_name=Rodrigo'
            '&child.last_name=Lucena'
            '&child.child.first_name=Polo'
            '&child.child.last_name=Norte'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        loaded = models.Parent.objects.get(id=parent.id)

        expect(loaded.child).not_to_be_null()
        expect(loaded.child.first_name).to_equal('Rodrigo')
        expect(loaded.child.last_name).to_equal('Lucena')

        expect(loaded.child.child).not_to_be_null()
        expect(loaded.child.child.first_name).to_equal('Polo')
        expect(loaded.child.child.last_name).to_equal('Norte')

    @testing.gen_test
    def test_can_save_parent_then_child(self):
        response = yield self.http_client.fetch(
            self.get_url('/parent/'),
            method='POST',
            body='name=Bernardo%20Heynemann'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')
        expect(response.headers).to_include('X-Created-Id')
        pk = response.headers['X-Created-Id']

        response = yield self.http_client.fetch(
            self.get_url('/parent/%s/child/' % pk),
            method='POST',
            body='first_name=Rodrigo&last_name=Lucena'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        parent = models.Parent.objects.get(id=pk)
        expect(parent.name).to_equal('Bernardo Heynemann')
        expect(parent.child).not_to_be_null()
        expect(parent.child.first_name).to_equal('Rodrigo')
        expect(parent.child.last_name).to_equal('Lucena')

    @testing.gen_test
    def test_can_delete_child_in_parent(self):
        child = models.Child(first_name='Foo', last_name='Bar')
        parent = models.Parent(name='Parent Name')
        parent.child = child
        parent.save()

        response = yield self.http_client.fetch(
            self.get_url('/parent/%s/child/' % (str(parent.id))),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        parent.reload()
        expect(parent.child).to_be_null()

    @testing.gen_test
    def test_can_save_user_team(self):
        team = models.Team.objects.create(name="test-team")
        user = models.User(name="Bernardo Heynemann", email="foo@bar.com")
        user.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/' % str(team.id)),
            method='POST',
            body='users[]=%s' % str(user.id)
        )

        team.reload()
        expect(response.code).to_equal(200)
        expect(team.users).to_length(1)
        expect(team.users[0].id).to_equal(user.id)

    @testing.gen_test
    def test_can_get_user_in_team(self):
        user = fix.UserFactory.create()
        team = models.Team.objects.create(name="test-team", users=[user])
        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/%s' % (team.id, user.id)),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj['email']).to_equal(user.email)
        expect(obj['name']).to_equal(user.name)
        expect(obj['slug']).to_equal(user.slug)

    @testing.gen_test
    def test_can_get_users_list_in_team(self):
        user = models.User(name='Bernardo Heynemann', email='heynemann@gmail.com')
        user.save()
        user2 = models.User(name='Rafael Floriano', email='rflorianobr@gmail.com')
        user2.save()
        team = models.Team.objects.create(name="test-team", users=[user, user2])

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/' % str(team.id)),
        )

        expect(response.code).to_equal(200)
        expect(response.body).not_to_be_empty()

        obj = utils.loads(response.body)
        expect(obj).to_length(2)
        expect(obj[0]['name']).to_equal('Bernardo Heynemann')
        expect(obj[0]['email']).to_equal('heynemann@gmail.com')
        expect(obj[1]['name']).to_equal('Rafael Floriano')
        expect(obj[1]['email']).to_equal('rflorianobr@gmail.com')

    @testing.gen_test
    def test_can_get_addresses_for_user_in_team(self):
        address = models.Address(street='Somewhere Else')
        address.save()
        user = models.User(name='Bernardo Heynemann', email='heynemann@gmail.com', addresses=[address])
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/%s/addresses' % (str(team.id), str(user.id))),
        )

        expect(response.code).to_equal(200)
        expect(response.body).not_to_be_empty()

        obj = utils.loads(response.body)
        expect(obj).to_length(1)
        expect(obj[0]['street']).to_equal(address.street)

    @testing.gen_test
    def test_can_update_addresses_for_user_in_team(self):
        address = models.Address(street='Somewhere Else')
        address.save()
        user = fix.UserFactory.create(addresses=[address])
        team = models.Team.objects.create(name="test-team", users=[user])

        # can't update reference field
        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/team/%s/users/%s/addresses/%s' % (str(team.id), str(user.id), str(address.id))),
                method='PUT',
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body='street=Somewhere'
            )
        expect(err.error.code).to_equal(400)

    @testing.gen_test
    def test_can_delete_user_in_team(self):
        user = fix.UserFactory.create()
        team = models.Team.objects.create(name="test-team", users=[user])
        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/%s' % (str(team.id), str(user.id))),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        user.reload()
        team.reload()
        expect(user).not_to_be_null()
        expect(team.users).to_be_empty()

    @testing.gen_test
    def test_can_delete_addresses_for_user_in_team(self):
        address = models.Address(street='Somewhere Else')
        address.save()
        user = models.User(name='Bernardo Heynemann', email='heynemann@gmail.com', addresses=[address])
        user.save()
        team = models.Team(name="test-team", users=[user])
        team.save()

        response = yield self.http_client.fetch(
            self.get_url('/team/%s/users/%s/addresses/%s' % (str(team.id), str(user.id), str(address.id))),
            method='DELETE'
        )

        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        user.reload()
        team.reload()
        expect(user).not_to_be_null()
        expect(user.addresses).to_be_empty()

    @testing.gen_test
    def test_can_save_child_in_parent2(self):
        parent = models.Parent2.objects.create(name="test-parent")

        response = yield self.http_client.fetch(
            self.get_url('/parent2/%s/children' % str(parent.id)),
            method='POST',
            body='first_name=Rodrigo&last_name=Lucena',
        )

        parent.reload()
        expect(response.code).to_equal(200)
        expect(parent.children).to_length(1)

    @testing.gen_test
    def test_can_get_child_in_parent2(self):
        child = models.Child(first_name='Foo', last_name='Bar')
        parent = models.Parent2.objects.create(name="test-team", children=[child])
        response = yield self.http_client.fetch(
            self.get_url('/parent2/%s/children/Foo' % (parent.id)),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj['first_name']).to_equal('Foo')
        expect(obj['last_name']).to_equal('Bar')

    @testing.gen_test
    def test_can_get_list_of_children_in_parent2(self):
        child = models.Child(first_name='Foo', last_name='Bar')
        parent = models.Parent2.objects.create(name="test-team", children=[child])
        response = yield self.http_client.fetch(
            self.get_url('/parent2/%s/children' % (parent.id)),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj).to_length(1)

    @testing.gen_test
    def test_can_update_child_in_parent2(self):
        child = models.Child(first_name='Foo', last_name='Bar')
        parent = models.Parent2.objects.create(name="test-team", children=[child])
        response = yield self.http_client.fetch(
            self.get_url('/parent2/%s/children/Foo' % (parent.id)),
            method='PUT',
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body='first_name=Rafael&last_name=Floriano'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        parent.reload()
        expect(parent.children[0].first_name).to_equal('Rafael')
        expect(parent.children[0].last_name).to_equal('Floriano')

    @testing.gen_test
    def test_can_delete_chold_of_user_in_team(self):
        child = models.Child(first_name='Foo', last_name='Bar')
        parent = models.Parent2.objects.create(name="test-team", children=[child])
        response = yield self.http_client.fetch(
            self.get_url('/parent2/%s/children/Foo' % (parent.id)),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        parent.reload()
        expect(parent).not_to_be_null()
        expect(parent.children).to_be_empty()

    @testing.gen_test
    def test_can_save_student_and_person(self):
        user = models.Person.objects.create(name="Bernardo")
        student = models.Student.objects.create(code="foo")

        response = yield self.http_client.fetch(
            self.get_url('/student/%s/person/' % str(student.id)),
            method='POST',
            body='person[]=%s' % user.id
        )

        student.reload()
        expect(response.code).to_equal(200)
        expect(student.person.name).to_equal('Bernardo')

    @testing.gen_test
    def test_can_get_person_in_student(self):
        person = models.Person.objects.create(name="test-student")
        student = models.Student.objects.create(code="foo", person=person)
        response = yield self.http_client.fetch(
            self.get_url('/student/%s/person/%s' % (student.id, person.id)),
        )
        expect(response.code).to_equal(200)
        obj = load_json(response.body)
        expect(obj['name']).to_equal(person.name)

        response = yield self.http_client.fetch(
            self.get_url('/student/%s/person' % (student.id)),
        )

        expect(response.code).to_equal(200)
        expect(response.body).not_to_be_empty()

        obj = load_json(response.body)
        expect(obj['name']).to_equal(person.name)

    @testing.gen_test
    def test_can_update_person_in_student(self):
        person = models.Person.objects.create(name="test-student")
        student = models.Student.objects.create(code="foo", person=person)
        response = yield self.http_client.fetch(
            self.get_url('/student/%s/person/%s' % (student.id, person.id)),
            method='PUT',
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body='name=Rafael'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        person.reload()
        expect(person.name).to_equal('Rafael')

    @testing.gen_test
    def test_can_delete_person_in_student(self):
        person = models.Person.objects.create(name="test-student")
        student = models.Student.objects.create(code="foo", person=person)
        response = yield self.http_client.fetch(
            self.get_url('/student/%s/person/%s' % (student.id, person.id)),
            method='DELETE'
        )
        expect(response.code).to_equal(200)
        expect(response.body).to_equal('OK')

        person.reload()
        student.reload()
        expect(person).not_to_be_null()
        expect(student.person).to_be_null()

    def test_can_get_tree_for_single_node(self):
        class Root(mongoengine.Document):
            prop = mongoengine.StringField()
            meta = {'collection': 'root_collection'}

        root_node = me.MongoEngineProvider.get_tree(Root)

        expect(root_node.name).to_equal('Root')
        expect(root_node.slug).to_equal('root')
        expect(root_node.target_name).to_equal('root_collection')
        expect(root_node.model_type).to_equal(Root)
        expect(root_node.is_multiple).to_be_false()
        expect(root_node.allows_create_on_associate).to_be_false()
        expect(root_node.children).to_length(2)
        expect(root_node.required_children).to_be_empty()

        child_node = root_node.children['id']
        expect(child_node.name).to_equal('id')
        expect(child_node.slug).to_equal('id')
        expect(child_node.target_name).to_equal('_id')
        expect(child_node.model_type).to_equal(None)
        expect(child_node.is_multiple).to_be_false()
        expect(child_node.allows_create_on_associate).to_be_false()
        expect(child_node.children).to_be_empty()
        expect(child_node.required_children).to_be_empty()

        child_node = root_node.children['prop']
        expect(child_node.name).to_equal('prop')
        expect(child_node.slug).to_equal('prop')
        expect(child_node.target_name).to_equal('prop')
        expect(child_node.model_type).to_equal(None)
        expect(child_node.is_multiple).to_be_false()
        expect(child_node.allows_create_on_associate).to_be_false()
        expect(child_node.children).to_be_empty()
        expect(child_node.required_children).to_be_empty()

    def test_can_get_tree_for_embedded_document(self):
        class Embedded(mongoengine.EmbeddedDocument):
            name = mongoengine.StringField()
            meta = {'collection': 'embedded_collection'}

        class Root(mongoengine.Document):
            prop = mongoengine.EmbeddedDocumentField(Embedded)
            meta = {'collection': 'root_collection'}

        root_node = me.MongoEngineProvider.get_tree(Root)

        child_node = root_node.children['prop']
        expect(child_node.name).to_equal('prop')
        expect(child_node.slug).to_equal('prop')
        expect(child_node.target_name).to_equal('prop')
        expect(child_node.model_type).to_equal(Embedded)
        expect(child_node.is_multiple).to_be_false()
        expect(child_node.allows_create_on_associate).to_be_true()
        expect(child_node.children).to_length(1)
        expect(child_node.required_children).to_be_empty()

        embedded_doc = child_node.children['name']
        expect(embedded_doc.name).to_equal('name')
        expect(embedded_doc.slug).to_equal('name')
        expect(embedded_doc.target_name).to_equal('name')
        expect(embedded_doc.model_type).to_be_null()
        expect(embedded_doc.is_multiple).to_be_false()
        expect(embedded_doc.allows_create_on_associate).to_be_false()
        expect(embedded_doc.children).to_be_empty()
        expect(embedded_doc.required_children).to_be_empty()

    def test_can_get_tree_for_reference_fields(self):
        class Reference(mongoengine.Document):
            name = mongoengine.StringField()
            meta = {'collection': 'reference_collection'}

        class Root(mongoengine.Document):
            prop = mongoengine.ReferenceField(Reference)
            meta = {'collection': 'root_collection'}

        root_node = me.MongoEngineProvider.get_tree(Root)

        child_node = root_node.children['prop']
        expect(child_node.name).to_equal('prop')
        expect(child_node.slug).to_equal('prop')
        expect(child_node.target_name).to_equal('prop')
        expect(child_node.model_type).to_equal(Reference)
        expect(child_node.is_multiple).to_be_false()
        expect(child_node.allows_create_on_associate).to_be_false()
        expect(child_node.children).to_length(2)
        expect(child_node.required_children).to_be_empty()

        reference_doc = child_node.children['name']
        expect(reference_doc.name).to_equal('name')
        expect(reference_doc.slug).to_equal('name')
        expect(reference_doc.target_name).to_equal('name')
        expect(reference_doc.model_type).to_be_null()
        expect(reference_doc.is_multiple).to_be_false()
        expect(reference_doc.allows_create_on_associate).to_be_false()
        expect(reference_doc.children).to_be_empty()
        expect(reference_doc.required_children).to_be_empty()

    def test_can_get_tree_for_lists_of_reference(self):
        class Reference(mongoengine.Document):
            name = mongoengine.StringField()
            meta = {'collection': 'reference_collection'}

        class Root(mongoengine.Document):
            prop = mongoengine.ListField(mongoengine.ReferenceField(Reference))
            meta = {'collection': 'root_collection'}

        root_node = me.MongoEngineProvider.get_tree(Root)

        child_node = root_node.children['prop']
        expect(child_node.name).to_equal('prop')
        expect(child_node.slug).to_equal('prop')
        expect(child_node.target_name).to_equal('prop')
        expect(child_node.model_type).to_equal(Reference)
        expect(child_node.is_multiple).to_be_true()
        expect(child_node.allows_create_on_associate).to_be_false()
        expect(child_node.children).to_length(2)
        expect(child_node.required_children).to_be_empty()

        reference_doc = child_node.children['name']
        expect(reference_doc.name).to_equal('name')
        expect(reference_doc.slug).to_equal('name')
        expect(reference_doc.target_name).to_equal('name')
        expect(reference_doc.model_type).to_be_null()
        expect(reference_doc.is_multiple).to_be_false()
        expect(reference_doc.allows_create_on_associate).to_be_false()
        expect(reference_doc.children).to_be_empty()
        expect(reference_doc.required_children).to_be_empty()

    def test_can_get_tree_for_lists_of_embedded_document(self):
        class Embedded(mongoengine.EmbeddedDocument):
            name = mongoengine.StringField()
            meta = {'collection': 'embedded_collection'}

        class Root(mongoengine.Document):
            prop = mongoengine.ListField(
                mongoengine.EmbeddedDocumentField(Embedded)
            )
            meta = {'collection': 'root_collection'}

        root_node = me.MongoEngineProvider.get_tree(Root)

        child_node = root_node.children['prop']
        expect(child_node.name).to_equal('prop')
        expect(child_node.slug).to_equal('prop')
        expect(child_node.target_name).to_equal('prop')
        expect(child_node.model_type).to_equal(Embedded)
        expect(child_node.is_multiple).to_be_true()
        expect(child_node.allows_create_on_associate).to_be_true()
        expect(child_node.children).to_length(1)
        expect(child_node.required_children).to_be_empty()

        embedded_doc = child_node.children['name']
        expect(embedded_doc.name).to_equal('name')
        expect(embedded_doc.slug).to_equal('name')
        expect(embedded_doc.target_name).to_equal('name')
        expect(embedded_doc.model_type).to_be_null()
        expect(embedded_doc.is_multiple).to_be_false()
        expect(embedded_doc.allows_create_on_associate).to_be_false()
        expect(embedded_doc.children).to_be_empty()
        expect(embedded_doc.required_children).to_be_empty()

    @testing.gen_test
    def test_can_get_user_list_with_custom_queryset(self):
        models.CustomQuerySet.objects.delete()
        user = models.CustomQuerySet(prop="Bernardo Heynemann")
        user.save()

        user = models.CustomQuerySet(prop="Rafael Floriano")
        user.save()

        response = yield self.http_client.fetch(
            self.get_url('/custom_query_set'),
        )

        expect(response.code).to_equal(200)
        expect(response.body).not_to_be_empty()

        obj = load_json(response.body)
        expect(obj).to_length(1)

        expect(obj[0]['prop']).to_equal('Bernardo Heynemann')

    @testing.gen_test
    def test_can_get_user_instance_with_custom_queryset(self):
        models.CustomQuerySet.objects.delete()
        user = models.CustomQuerySet(prop="Bernardo Heynemann")
        user.save()

        user = models.CustomQuerySet(prop="Rafael Floriano")
        user.save()

        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/custom_query_set/%s' % user.id),
            )
        expect(err.error.code).to_equal(404)

    @testing.gen_test
    def test_can_create_unique_user(self):
        models.UniqueUser.objects.delete()

        models.UniqueUser(name="unique").save()

        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/unique_user/'),
                method='POST',
                body='name=unique'
            )

        expect(err.error.code).to_equal(409)
        encoding = locale.getdefaultlocale()[1]
        expect('unique keys' in err.error.response.body.decode(encoding)).to_be_true()

    @testing.gen_test
    def test_can_create_invalid_user(self):
        models.ValidationUser.objects.delete()
        models.UniqueUser.objects.delete()

        user = models.UniqueUser(name="unique")
        user.save()

        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/validation_user/'),
                method='POST',
                body='items[]=%s' % user.id
            )

        expect(err.error.code).to_equal(400)
        expect(err.error.response.body).to_equal("ValidationError (ValidationUser:None) (Field is required: ['name'])")

    @testing.gen_test
    def test_cant_remove_invalid_association(self):
        models.ValidationUser.objects.delete()
        models.UniqueUser.objects.delete()

        user = models.UniqueUser(name="unique")
        user.save()

        validation = models.ValidationUser(name="validation", items=[user])
        validation.save()

        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/validation_user/%s/items/%s' % (str(validation.id), str(user.id))),
                method='DELETE'
            )

        expect(err.error.code).to_equal(400)
        expect(err.error.response.body).to_equal("ValidationError (ValidationUser:%s) (Field is required and cannot be empty: ['items'])" % (validation.id))

    @testing.gen_test
    def test_cant_save_when_invalid_association(self):
        models.ValidationUser.objects.delete()
        models.UniqueUser.objects.delete()

        user = models.UniqueUser(name="unique")
        user.save()

        user2 = models.UniqueUser(name="unique2")
        user2.save()

        validation = models.ValidationUser(name="validation", items=[user])
        validation.save()

        err = expect.error_to_happen(HTTPError)
        with err:
            yield self.http_client.fetch(
                self.get_url('/validation_user/%s/items/' % str(validation.id)),
                method='POST',
                body='items[]=%s' % user2.id
            )

        expect(err.error.code).to_equal(400)
        expect(err.error.response.body).to_equal("ValidationError (ValidationUser:%s) (something went wrong: ['__all__'])" % (validation.id))
