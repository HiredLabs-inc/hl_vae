"""DES-011: dimension tables."""

from django.test import TestCase

from .models import (
    Author,
    Discipline,
    Institution,
    Publication,
    Subject,
    Topic,
    Work,
    WorkType,
)

NAMED_MODELS = [WorkType, Institution, Publication, Subject, Discipline]


class DimensionTableStrTests(TestCase):
    def test_named_models_str(self):
        for model in NAMED_MODELS:
            with self.subTest(model=model.__name__):
                obj = model.objects.create(name="Example")
                self.assertEqual(str(obj), f"Example {obj.id}")

    def test_topic_str(self):
        topic = Topic.objects.create(
            subject=Subject.objects.create(name="Civil Engineering"),
            discipline=Discipline.objects.create(name="Engineering"),
        )
        self.assertEqual(str(topic), f"Engineering , Civil Engineering , #{topic.id}")


class AuthorWorkTests(TestCase):
    def test_author_str(self):
        author = Author.objects.create(name="Ada Lovelace")
        self.assertEqual(str(author), "Ada Lovelace")

    def test_work_str(self):
        work = Work.objects.create(
            title="On Engines", author=Author.objects.create(name="Ada Lovelace")
        )
        self.assertEqual(str(work), "Title: On Engines")

    def test_work_defaults(self):
        work = Work.objects.create(
            title="Draft", author=Author.objects.create(name="Ada Lovelace")
        )
        self.assertIs(work.is_published, False)
        self.assertIs(work.is_approved, False)
        self.assertEqual(work.link, "")
