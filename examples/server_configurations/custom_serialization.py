# custom_serialization.py - using Marshmallow serialization with Flask-Restless
#
# Copyright 2011 Lincoln de Sousa <lincoln@comum.org>.
# Copyright 2012, 2013, 2014, 2015, 2016 Jeffrey Finkelstein
#           <jeffrey.finkelstein@gmail.com> and contributors.
#
# This file is part of Flask-Restless.
#
# Flask-Restless is distributed under both the GNU Affero General Public
# License version 3 and under the 3-clause BSD license. For more
# information, see LICENSE.AGPL and LICENSE.BSD.
"""Using Marshmallow for serialization in Flask-Restless.

This script is an example of using `Marshmallow`_ to provide custom
serialization (and the corresponding deserialization) from SQLAlchemy
models to Python dictionaries that will eventually become JSON API
responses to the client. Specifically, this example uses the
`marshmallow-jsonapi`_ library to create serialization/deserialization
functions for use with Flask-Restless.

There are some problems with this approach. You will need to specify
some configuration twice, once for marshmallow-jsonapi and once for
Flask-Restless. For example, you must provide a custom "collection name"
as both the class-level attribute :attr:`Meta.type_` and as the
*collection_name* keyword argument to :meth:`APIManager.create_api`. For
another example, you must specify the URLs for relationships and related
resources directly in the schema definition, and thus these must match
EXACTLY the URLs created by Flask-Restless. The URLs created by
Flask-Restless are fairly predictable, so this requirement, although not
ideal, should not be too challenging.

(This example might have used the `marshmallow-sqlalchemy`_ model to
mitigate some of these issues, but there does not seem to be an easy way
to combine these two Marshmallow layers together.)

To install the necessary requirements for this example, run::

    pip install flask-restless==1.0.0b2.dev0 flask-sqlalchemy==2.3.2 marshmallow-jsonapi==0.16.0

To run this script from the current directory::

    python -m custom_serialization

This will run a Flask server at ``http://localhost:5000``. You can then
make requests using any web client.

.. _Marshmallow: https://marshmallow.readthedocs.org
.. _marshmallow-sqlalchemy: https://marshmallow-sqlalchemy.readthedocs.org
.. _marshmallow-jsonapi: https://marshmallow-jsonapi.readthedocs.org

"""
from flask import Flask
from flask_restless import APIManager
from flask_restless import DefaultSerializer
from flask_restless import DefaultDeserializer
from flask_sqlalchemy import SQLAlchemy
from marshmallow import post_load
from marshmallow_jsonapi import fields
from marshmallow_jsonapi import Schema
from marshmallow_jsonapi.fields import Relationship
import json
from sqlalchemy.ext.associationproxy import (
    _AssociationDict, _AssociationList, _AssociationSet)
from sqlalchemy.orm.collections import (
    InstrumentedList, MappedCollection)

# Flask application and database configuration

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-SQLAlchemy model definitions #

class Person(db.Model):
    __tablename__ = 'person'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode)
    articles = db.relationship('Article', back_populates='author')


class Article(db.Model):
    __tablename__ = 'article'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Unicode)
    author_id = db.Column(db.Unicode, db.ForeignKey(Person.id))
    author = db.relationship(Person, back_populates='articles')


# Marshmallow schema definitions #

class PersonSchema(Schema):

    class Meta:
        model = Person
        type_ = 'person'
        sqla_session = db.session
        strict = True

    id = fields.Integer(dump_only=True)
    name = fields.Str()

    articles = fields.Relationship(
        self_url='/api/person/{personid}/relationships/articles',
        self_url_kwargs={'personid': '<id>'},
        related_url='/api/article/{articleid}',
        related_url_kwargs={'articleid': '<id>'},
        many=True,
        include_data=True,
        include_resource_linkage=True,
        type_='article',
        schema='ArticleSchema'
    )

    @post_load
    def make_person(self, data):
        return Person(**data)


class ArticleSchema(Schema):

    class Meta:
        model = Article
        type_ = 'article'
        sqla_session = db.session
        strict = True

    id = fields.Integer(dump_only=True)
    title = fields.Str()

    author = fields.Relationship(
        self_url='/api/article/{articleid}/relationships/author',
        self_url_kwargs={'articleid': '<id>'},
        related_url='/api/person/{personid}',
        related_url_kwargs={'personid': '<id>'},
        include_data=True,
        type_='person',
        schema='PersonSchema'
    )

    @post_load
    def make_article(self, data):
        return Article(**data)


def is_list_like(rel_instance):
    return (isinstance(rel_instance, list) or isinstance(rel_instance, set)
            or isinstance(rel_instance, _AssociationList)
            or isinstance(rel_instance, _AssociationSet)
            or isinstance(rel_instance, InstrumentedList))
# Serializer and deserializer classes #

class MarshmallowSerializer(DefaultSerializer):

    schema_class = None

    def serialize(self, instance, only=None):
        schema = self.schema_class(only=only)
        return schema.dump(instance).data

    def serialize_many(self, instances, only=None):
        schema = self.schema_class(many=True, only=only)
        return schema.dump(instances).data

class MarshmallowDeserializer(DefaultDeserializer):

    schema_class = None

    # def _process_and_rm_existing(self, ):

    def deserialize(self, document):
        # import json
        schema = self.schema_class()

        # documentjson = json.loads(document)

        # inspired by flask-rest-jsonapi
        rltnshps = [key for (key, value) in schema._declared_fields.items() if isinstance(value, Relationship)]

        # posted_rltns = document.get('relationships')
        posted_rltns = document.get('data').get('relationships')
        existing = []
        for (key, val) in posted_rltns.items():
            data = val.get('data')
            data = data if (isinstance(data, list)) else [data]

            for i, x in enumerate(data):
                id = x.get('id')
                rltd_model = getattr(self.model, key).property.mapper.class_
                exist = self.session.query(rltd_model).get(id)
                if exist != None:
                    existing.append({key: exist})

                del document['data'].get('relationships')[key]['data'][i]
                # d = {}
                # d[key] = x.get('id')
                # ids.append(d)


        # existing = []
        # for id in ids:
        #     field, val = list(id.items())[0]
        #     rltd_model = getattr(self.model, field).property.mapper.class_
        #     exist = self.session.query(rltd_model).get(val)
        #     if exist != None:
        #         existing.append(exist)


        # for rlt in rltnshps:
        #     rltattr = getattr(schema.Meta.model, rlt)
        deserialized_inst = schema.load(document).data

        for ex in existing:
            k, v = ex.items()[0]
            field = getattr(deserialized_inst, k)

            if is_list_like(field):
                field.append(v)


        # json =
        # for (key, val) in self.schema_class._declared_fields.items():
        #     print('key', key)
        return schema.load(document).data

    def deserialize_many(self, document):
        schema = self.schema_class(many=True)
        return schema.load(document).data


class PersonSerializer(MarshmallowSerializer):
    schema_class = PersonSchema


class PersonDeserializer(MarshmallowDeserializer):
    schema_class = PersonSchema


class ArticleSerializer(MarshmallowSerializer):
    schema_class = ArticleSchema


class ArticleDeserializer(MarshmallowDeserializer):
    schema_class = ArticleSchema


if __name__ == '__main__':
    db.create_all()
    manager = APIManager(app, flask_sqlalchemy_db=db)

    manager.create_api(Person, methods=['GET', 'PATCH', 'POST'],
                       serializer_class=PersonSerializer,
                       deserializer_class=PersonDeserializer, allow_to_many_replacement=True)
    manager.create_api(Article, methods=['GET', 'PATCH', 'POST'],
                       serializer_class=ArticleSerializer,
                       deserializer_class=ArticleDeserializer, allow_to_many_replacement=True)

    app.run()
