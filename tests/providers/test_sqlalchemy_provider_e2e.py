#!/usr/bin/python
# -*- coding: utf-8 -*-

# This file is part of bzz.
# https://github.com/heynemann/bzz

# Licensed under the MIT license:
# http://www.opensource.org/licenses/MIT-license
# Copyright (c) 2014 Bernardo Heynemann heynemann@gmail.com

import types

import cow.server as server
import cow.plugins.sqlalchemy_plugin as sqlalchemy_plugin
from preggy import expect
import derpconf.config as config
import tornado.web
import sqlalchemy as sa
import sqlalchemy.sql.functions as func
import sqlalchemy.orm as orm

import bzz
from bzz.providers.sqlalchemy_provider import Base
import bzz.signals as signals
import bzz.utils as utils
import tests.base as base


RESPONSE_400 = '<html><title>400:badrequest</title><body>400:badrequest</body></html>'


class SQLAlchemyE2ETestCase(base.ApiTestCase):
    def __get_test_data(self):
        to_json = lambda body: load_json(body)  # NOQA - Syntatic Sugar

        return [
            ('GET', '/user', {}, 200, to_json, []),
            ('POST', '/user', dict(body="name=test%20user&age=32"), 200, None, None),
            ('GET', '/user', {}, 200, to_json, self.__assert_user_data(name="test user", age=32)),
            ('GET', '/user/test%20user', {}, 200, to_json, self.__assert_user_data(name="test user", age=32)),
            ('PUT', '/user/test%20user', dict(body="age=31"), 200, None, None),
            ('GET', '/user/test%20user', {}, 200, to_json, self.__assert_user_data(name="test user", age=31)),
            ('POST', '/user', dict(body="name=test-user2&age=32"), 200, None, None),
            ('DELETE', '/user/test-user2', {}, 200, None, None),
            ('GET', '/user', {}, 200, to_json, self.__assert_len(1)),
            ('GET', '/team', {}, 200, to_json, []),
            ('POST', '/team', dict(body="code=team-1&owner=test%20user"), 200, None, None),
            ('GET', '/team/team-1', {}, 200, to_json, self.__assert_team_data(name="team-1", owner="test user")),
            ('GET', '/user/test%20user', {}, 200, to_json, self.__assert_user_data(name="test user", age=31, team_length=1)),
            ('POST', '/user', dict(body="name=test-user3&age=32"), 200, None, None),
            ('PUT', '/team/team-1', dict(body="owner=test-user3"), 200, None, None),
            ('PUT', '/team/team-1', dict(body="members[]=test-user3"), 400, None, RESPONSE_400),
            ('GET', '/team/team-1', {}, 200, to_json, self.__assert_team_data(name='team-1', member_count=0)),
            ('POST', '/team', dict(body="code=team-2&owner=test%20user&members[]=test%20user"), 200, None, None),
            ('GET', '/team/team-2', {}, 200, to_json, self.__assert_team_data(name='team-2', member_count=1)),
            ('POST', '/team', dict(body="code=team-3&owner=test%20user&members[]=test%20user&members[]=test-user3"),
                200, None, None),
            ('GET', '/team/team-3', {}, 200, to_json, self.__assert_team_data(name='team-3', member_count=2)),
            ('DELETE', '/team/team-2', {}, 200, None, None),
            ('DELETE', '/team/team-3', {}, 200, None, None),
            ('GET', '/team', {}, 200, to_json, self.__assert_len(1)),
            ('POST', '/team/team-1/members', dict(body="members[]=test%20user"), 200, None, None),
            ('GET', '/team/team-1/members', {}, 200, to_json, self.__assert_len(1)),
            ('POST', '/user', dict(body="name=test-user4&age=32"), 200, None, None),
            ('POST', '/team/team-1/members', dict(body="members[]=test-user4"), 200, None, None),
            ('DELETE', '/team/team-1/members/test-user4', {}, 200, None, None),
            ('PUT', '/team/team-1/members/test-user4', dict(body=""), 400, None, RESPONSE_400),
            ('GET', '/team/team-1/members', {}, 200, to_json, self.__assert_len(1)),
            ('GET', '/user/test-user4', {}, 200, to_json, self.__assert_user_data(name="test-user4", age=32)),
        ]

    def test_end_to_end_flow(self):
        data = self.__get_test_data()

        print("")
        print("")
        print("")
        print("Doing end-to-end test:")
        print("")
        for url_arguments in data:
            self.validate_request(url_arguments)
        print("")

    def setUp(self):
        super(SQLAlchemyE2ETestCase, self).setUp()
        self.server.application.db = self.server.application.get_sqlalchemy_session()
        Base.metadata.create_all(bind=self.server.application.db.connection())
        signals.post_create_instance.receivers = {}
        signals.post_update_instance.receivers = {}
        signals.post_delete_instance.receivers = {}
        self.server.application.db.execute("truncate table EndToEndUserTeamTable")
        self.server.application.db.query(EndToEndTeam).delete()
        self.server.application.db.query(EndToEndUser).delete()

    def get_config(self):
        return dict(
            SQLALCHEMY_AUTO_FLUSH=True,
            SQLALCHEMY_POOL_MAX_OVERFLOW=1,
            SQLALCHEMY_POOL_SIZE=1,
            SQLALCHEMY_CONNECTION_STRING="mysql://root@localhost/test_bzz"
        )

    def get_server(self):
        cfg = config.Config(**self.get_config())
        self.server = TestServer(config=cfg)
        return self.server

    def __assert_project_data(self, name=None, module=None):
        def handle(obj):
            if name is not None:
                expect(obj['name']).to_be_like(name)

            if module is not None:
                expect(obj['module']).not_to_be_null()
                expect(obj['module']['name']).to_be_like(module)

        return handle

    def __assert_module_data(self, name=None):
        def handle(obj):
            if name is not None:
                expect(obj['name']).to_be_like(name)

        return handle

    def __assert_user_data(self, created_at=None, age=None, id_=None, name=None, team_length=None):
        def handle(obj):
            if isinstance(obj, (list, tuple)):
                obj = obj[0]

            if created_at is not None:
                expect(obj['created_at']).to_be_like(created_at)

            if age is not None:
                expect(obj['age']).to_equal(age)

            if id_ is not None:
                expect(obj['id']).to_be_like(id_)

            if name is not None:
                expect(obj['name']).to_equal(name)

            if team_length is not None:
                expect(obj['teams']).to_length(team_length)
        return handle

    def __assert_team_data(self, owner=None, name=None, member_count=None):
        def handle(obj):
            if isinstance(obj, (list, tuple)):
                obj = obj[0]

            if owner is not None:
                expect(obj['owner']).not_to_be_null()
                expect(obj['owner']['name']).to_equal(owner)

            if name is not None:
                expect(obj['code']).to_equal(name)

            if member_count is not None:
                expect(obj['members']).to_length(member_count)

        return handle

    def __assert_len(self, expected_length):
        def handle(obj):
            expect(obj).not_to_be_null()
            expect(obj).to_be_instance_of(list)
            expect(obj).to_length(expected_length)
        return handle

    def validate_request(self, url_arguments):
        method, url, options, expected_status_code, transform_body, expected_body = url_arguments

        print(">>>>>>>>>>>>>>>>>> B %s %s..." % (method, url))
        self.http_client.fetch(
            self.get_url(url),
            method=method,
            callback=self.stop,
            **options
        )
        response = self.wait()
        # import ipdb; ipdb.set_trace()
        expect(response.code).to_equal(expected_status_code)

        body = response.body
        if transform_body is not None:
            body = transform_body(response.body)

        if expected_body and isinstance(expected_body, types.FunctionType):
            expected_body(body)
        elif expected_body:
            expect(body).to_be_like(expected_body)

        print(">>>>>>>>>>>>>>>>>> A %s %s - %s" % (method, url, response.code))


def load_json(json_string):
    try:
        return utils.loads(json_string)
    except ValueError:
        return utils.loads(json_string.decode('utf-8'))


members_association_table = sa.Table(
    'EndToEndUserTeamTable', Base.metadata,
    sa.Column('user_id', sa.Integer, sa.ForeignKey('EndToEndUserTable.id')),
    sa.Column('team_id', sa.Integer, sa.ForeignKey('EndToEndTeamTable.id')),
)


class EndToEndUser(Base):
    __tablename__ = 'EndToEndUserTable'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(2000))
    age = sa.Column(sa.Integer)
    created_at = sa.Column(sa.DateTime, nullable=False, default=func.now())

    @classmethod
    def get_id_field_name(self):
        return EndToEndUser.name

    def to_dict(self):
        return {
            'name': self.name,
            'age': self.age,
            'teams': [team.code for team in self.teams],
        }


class EndToEndTeam(Base):
    __tablename__ = "EndToEndTeamTable"

    id = sa.Column(sa.Integer, primary_key=True)
    code = sa.Column(sa.String(2000))

    owner_id = sa.Column(sa.Integer, sa.ForeignKey('EndToEndUserTable.id'))
    owner = orm.relationship(EndToEndUser, backref='teams')

    members = orm.relationship(EndToEndUser, secondary=members_association_table, backref="member_of")

    @classmethod
    def get_id_field_name(self):
        return EndToEndTeam.code

    def to_dict(self):
        return {
            'code': self.code,
            'owner': {
                'name': self.owner.name
            },
            'members': [member.name for member in self.members],
        }


class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(bzz.__version__)


class TestServer(server.Server):
    def get_plugins(self):
        return [
            sqlalchemy_plugin.SQLAlchemyPlugin
        ]

    def get_handlers(self):
        routes = [
            bzz.ModelHive.routes_for('sqlalchemy', EndToEndUser, resource_name="user"),
            bzz.ModelHive.routes_for('sqlalchemy', EndToEndTeam, resource_name="team"),
            ('/version', VersionHandler),
        ]
        return bzz.flatten(routes)
