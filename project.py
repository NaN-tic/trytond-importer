from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.i18n import gettext
from .tools import ImporterModel, Cache, Setup


class ImporterProjectStatus(ImporterModel):
    'Importer Project Status'
    __name__ = 'importer.project.work.status'

    name = fields.Char('Name')
    active = fields.Boolean('Active')
    default = fields.Boolean('Default')
    count = fields.Boolean('Count')
    sequence = fields.Integer('Sequence')
    project = fields.Boolean('Project')
    task = fields.Boolean('Task')
    progress = fields.Float('Progress')

    @classmethod
    def importer_status_hook(cls, record, status):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ProjectStatus = pool.get('project.work.status')

        setup = Setup.get()

        to_save = []
        for record in records:
            setup.current_record = record

            status = ProjectStatus()
            if 'name' in setup.fields:
                status.name = record.name
            if 'active' in setup.fields:
                status.active = record.active
            if 'default' in setup.fields:
                status.default = record.default
            if 'count' in setup.fields:
                status.count = record.count
            if 'sequence' in setup.fields:
                status.sequence = record.sequence
            types = []
            if 'project' in setup.fields:
                types.append('project')
            if 'task' in setup.fields:
                types.append('task')
            if types:
                status.types = types
            if 'progress' in setup.fields:
                status.progress = record.progress
            cls.importer_status_hook(record, status)
            to_save.append((status, record))

        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class ImporterProjectWorkflow(ImporterModel):
    'Importer Project Workflow'
    __name__ = 'importer.project.work.workflow'

    name = fields.Char('Name')
    status = fields.Char('Status')
    sequence = fields.Integer('Sequence')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.status = Cache('project.work.status', 'name')

    @classmethod
    def importer_workflow_hook(cls, record, workflow):
        pass

    @classmethod
    def importer_workflow_line_hook(cls, record, line):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ProjectWorkflow = pool.get('project.work.workflow')
        ProjectWorkflowLine = pool.get('project.work.workflow.line')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        to_save_workflow_line = []
        previous_workflow = None
        for record in records:
            line = ProjectWorkflowLine()
            setup.current_record = record

            if previous_workflow and previous_workflow.name == record.name:
                workflow = previous_workflow
            else:
                workflow = ProjectWorkflow()
                if 'name' in setup.fields:
                    workflow.name = record.name
                previous_workflow = workflow
            line.workflow = workflow

            if 'status' in setup.fields:
                status = cache.status.get(record.status)
                if not status:
                    setup.error(gettext('importer.msg_status_not_found',
                        status=record.status))
                    continue
                line.status = status
            if 'sequence' in setup.fields:
                line.sequence = record.sequence
            cls.importer_workflow_hook(record, workflow)
            cls.importer_workflow_line_hook(record, line)
            to_save_workflow_line.append((line, record))
            to_save.append((workflow, record))

        cls.importer_save(to_save)
        cls.importer_save(to_save_workflow_line)
        return [x[0] for x in to_save]


class ImporterProjectTracker(ImporterModel):
    'Importer Project Tracker'
    __name__ = 'importer.project.work.tracker'

    name = fields.Char('Name')
    active = fields.Boolean('Active')
    workflow = fields.Char('Workflow')
    group = fields.Char('Group')

    @classmethod
    def importer_start(cls):
        super().importer_start()
        cache = Setup.get().cache
        cache.workflows = Cache('project.work.workflow', 'name')
        cache.groups = Cache('res.group', 'name')

    @classmethod
    def importer_tracker_hook(cls, record, tracker):
        pass

    @classmethod
    def importer_import(cls, records):
        pool = Pool()
        ProjectTracker = pool.get('project.work.tracker')

        setup = Setup.get()
        cache = setup.cache

        to_save = []
        for record in records:
            setup.current_record = record

            tracker = ProjectTracker()
            if 'name' in setup.fields:
                tracker.name = record.name
            if 'active' in setup.fields:
                tracker.active = record.active
            if 'workflow' in setup.fields:
                workflow = cache.workflows.get(record.workflow)
                if not workflow:
                    setup.error(gettext('importer.msg_project_workflow_not_found',
                        workflow=record.workflow))
                    continue
                tracker.workflow = workflow
            if 'group' in setup.fields:
                group = cache.groups.get(record.group)
                if not group:
                    setup.error(gettext('importer.msg_project_group_not_found',
                        group=record.group))
                    continue
                tracker.group = group
            cls.importer_tracker_hook(record, tracker)
            to_save.append((tracker, record))

        cls.importer_save(to_save)
        return [x[0] for x in to_save]


class Importer(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'project_status': {
                    'string': 'Project Status',
                    'model': 'importer.project.work.status',
                    },
                'project_workflow': {
                    'string': 'Project Workflow',
                    'model': 'importer.project.work.workflow',
                    },
                })
        return methods


class ProjectTrackerImporter(metaclass=PoolMeta):
    __name__ = 'importer'

    @classmethod
    def _get_methods(cls):
        methods = super()._get_methods()
        methods.update({
                'project_tracker': {
                    'string': 'Project Tracker',
                    'model': 'importer.project.work.tracker',
                    }
                })
        return methods
