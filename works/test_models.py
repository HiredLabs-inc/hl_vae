"""DES-011: dimension tables."""

from django.test import TestCase

from .models import Discipline, Institution, Publication, Subject, Topic, WorkType

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
