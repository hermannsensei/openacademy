# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import tools
from odoo import models, fields, api, exceptions, _

class openacademy(models.Model):
    _name = 'openacademy.openacademy'

    name = fields.Char()
    value = fields.Integer()
    value2 = fields.Float(compute="_value_pc", store=True)
    description = fields.Text()

    @api.depends('value')
    def _value_pc(self):
        self.value2 = float(self.value) / 100

class Course(models.Model):
    _name = 'openacademy.course'
    _description = "OpenAcademy Courses"

    name = fields.Char(string="Title", required=True)
    description = fields.Text()
    responsible_id = fields.Many2one('res.users',
        ondelete='set null', string="Responsible", index=True)
    session_ids = fields.One2many(
        'openacademy.session', 'course_id', string="Sessions")

    @api.multi
    def copy(self, default=None):
        default = dict(default or {})

        copied_count = self.search_count(
            [('name', '=like', _(u"Copy of {}%").format(self.name))])
        if not copied_count:
            new_name = _(u"Copy of {}").format(self.name)
        else:
            new_name = _(u"Copy of {} ({})").format(self.name, copied_count)

        default['name'] = new_name
        return super(Course, self).copy(default)

    _sql_constraints = [
        ('name_description_check',
         'CHECK(name != description)',
         "The title of the course should not be the description"),

        ('name_unique',
         'UNIQUE(name)',
         "The course title must be unique"),
    ]


class Session(models.Model):
    _name = 'openacademy.session'
    _description = "OpenAcademy Sessions"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(required=True,track_visibility='onchange')
    start_date = fields.Date(default=fields.Date.today)
    duration = fields.Float(digits=(6, 2), help="Duration in days")
    seats = fields.Integer(string="Number of seats",track_visibility='onchange')
    active = fields.Boolean(default=True)
    color = fields.Integer()
    instructor_id = fields.Many2one('res.partner', string="Instructor",
         domain=['|', ('instructor', '=', True),
                ('category_id.name', 'ilike', "Teacher")],track_visibility='onchange')

    course_id = fields.Many2one('openacademy.course',
                                ondelete='cascade', string="Course", required=True)
    attendee_ids = fields.Many2many('res.partner', string="Attendees")
    add_date = fields.Datetime(string = 'Adding Date',default=fields.Datetime.today)

    taken_seats = fields.Float(string="Taken seats", compute='_taken_seats')
    end_date = fields.Date(string="End Date", store=True,
                           compute='_get_end_date', inverse='_set_end_date')

    attendees_count = fields.Integer(
        string="Attendees count", compute='_get_attendees_count', store=True)
    state = fields.Selection([
        ('draft', "Draft"),
        ('confirmed', "Confirmed"),
        ('done', "Done"),
    ], default='draft',track_visibility='onchange')



    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_confirm(self):
        self.state = 'confirmed'

    @api.multi
    def action_done(self):
        self.state = 'done'
        env = self.env['mail.followers']
        domain = []
        env.search(domain).unlink()
        self.env['mail.followers'].create({
            'res_id': self.id,
            'res_model': 'openacademy.session',
            'partner_id': self.instructor_id.id
        })

    @api.depends('seats', 'attendee_ids')
    def _taken_seats(self):
        for r in self:
            if not r.seats:
                r.taken_seats = 0.0
            else:
                r.taken_seats = 100.0 * len(r.attendee_ids) / r.seats

    @api.onchange('seats', 'attendee_ids')
    def _verify_valid_seats(self):
        if self.seats < 0:
            return {
                'warning': {
                    'title': _("Incorrect 'seats' value"),
                    'message': _("The number of available seats may not be negative"),
                },
            }
        if self.seats < len(self.attendee_ids):
            return {
                'warning': {
                    'title': _("Too many attendees"),
                    'message': _("Increase seats or remove excess attendees"),
                },
            }

    @api.depends('start_date', 'duration')
    def _get_end_date(self):
        for r in self:
            if not (r.start_date and r.duration):
                r.end_date = r.start_date
                continue

            # Add duration to start_date, but: Monday + 5 days = Saturday, so
            # subtract one second to get on Friday instead
            start = fields.Datetime.from_string(r.start_date)
            duration = timedelta(days=r.duration, seconds=-1)
            r.end_date = start + duration

    def _set_end_date(self):
        for r in self:
            if not (r.start_date and r.end_date):
                continue

            # Compute the difference between dates, but: Friday - Monday = 4 days,
            # so add one day to get 5 days instead
            start_date = fields.Datetime.from_string(r.start_date)
            end_date = fields.Datetime.from_string(r.end_date)
            r.duration = (end_date - start_date).days + 1

    @api.depends('attendee_ids')
    def _get_attendees_count(self):
        for r in self:
            r.attendees_count = len(r.attendee_ids)



    @api.constrains('instructor_id', 'attendee_ids')
    def _check_instructor_not_in_attendees(self):
        for r in self:
            if r.instructor_id and r.instructor_id in r.attendee_ids:
                raise exceptions.ValidationError(_("A session's instructor can't be an attendee"))

class SessionReport(models.Model):
    _name = 'openacademy.report'
    _description = "Session Report"
    _auto = False

    course_name = fields.Char(string="Title", readonly=True)
    name = fields.Char('Name', readonly=True)
    duration = fields.Float(digits=(6, 2), readonly=True, help="Duration in days")
    seats = fields.Integer(string="Number of seats", readonly=True)
    end_date = fields.Datetime(string="End Date", readonly=True)
    create_date = fields.Datetime(string="Create Date", readonly=True)
    session_counts = fields.Integer(string="Nombre de session", readonly=True)
    attendees_counts = fields.Integer(string="Nombre de participants", readonly=True)
    start_date = fields.Datetime(string="Create Date of session", readonly=True)
    add_date = fields.Datetime(string="Last modification date", readonly=True)
    session_by_course = fields.Float(string = "Nombre de session par cours", readonly=True)
    mean_duration = fields.Float(string = "Duree moyenne", readonly=True)
    course_id = fields.Many2one('openacademy.course',
                                ondelete='cascade', string="Course", required=True)
    session_id = fields.Many2one('openacademy.session',
                                ondelete='cascade', string="Course", required=True)
    instructor_id = fields.Many2one('res.partner', string="Instructor",
                                    domain=['|', ('instructor', '=', True),
                                            ('category_id.name', 'ilike', "Teacher")])

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
                c.id as id,
                c.create_date as create_date,
                s.attendees_count as attendees_counts,
                c.id as course_id,
                s.id as session_id,
                count(s.id) as session_counts ,
                s.name as name,
                s.start_date as start_date,
                s.end_date as end_date,
                s.add_date as add_date,
                sum(s.duration) as duration,
                sum(s.seats) as seats,
                count(s.id)/count(c.id) as session_by_course,
                avg(end_date - start_date) as mean_duration
            """

        for field in fields.values():
            select_ += field

        from_ = """
                    openacademy_course as c
                    left join openacademy_session as s  on  s.course_id = c.id
                    %s
            """ % from_clause

        groupby_ = """
                c.id,
                s.id
                 %s
            """ % (groupby)

        return '%s (SELECT %s FROM %s  GROUP BY %s)' % (with_, select_, from_, groupby_)

    @api.model_cr
    def init(self):
        print('-------------------------------')
        print('-------------------------------')
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))



