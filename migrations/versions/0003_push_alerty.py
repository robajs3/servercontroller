"""push_alerty

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def _missing(name):
    # baza przejęta z wcześniejszych etapów (create_all) może już mieć te tabele
    return not sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    if _missing('push_subscriptions'):
        op.create_table('push_subscriptions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('endpoint', sa.String(length=1000), nullable=False),
            sa.Column('p256dh', sa.String(length=200), nullable=False),
            sa.Column('auth', sa.String(length=100), nullable=False),
            sa.Column('ua', sa.String(length=200), nullable=True),
            sa.Column('created', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_ok', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('endpoint'))
        op.create_index('ix_push_subscriptions_user_id', 'push_subscriptions', ['user_id'])
    if _missing('alert_state'):
        op.create_table('alert_state',
            sa.Column('key', sa.String(length=200), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('announced', sa.Boolean(), nullable=False),
            sa.Column('pending_since', sa.DateTime(timezone=True), nullable=True),
            sa.Column('since', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_notified', sa.DateTime(timezone=True), nullable=True),
            sa.Column('title', sa.String(length=160), nullable=True),
            sa.Column('detail', sa.String(length=300), nullable=True),
            sa.PrimaryKeyConstraint('key'))
    if _missing('alert_events'):
        op.create_table('alert_events',
            sa.Column('id', sa.BigInteger(), nullable=False),
            sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
            sa.Column('key', sa.String(length=200), nullable=False),
            sa.Column('kind', sa.String(length=8), nullable=False),
            sa.Column('title', sa.String(length=160), nullable=False),
            sa.Column('detail', sa.String(length=300), nullable=True),
            sa.Column('pushed', sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint('id'))
        op.create_index('ix_alert_events_ts', 'alert_events', ['ts'])
    if _missing('alert_settings'):
        op.create_table('alert_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('alert_settings')
    op.drop_index('ix_alert_events_ts', table_name='alert_events')
    op.drop_table('alert_events')
    op.drop_table('alert_state')
    op.drop_index('ix_push_subscriptions_user_id', table_name='push_subscriptions')
    op.drop_table('push_subscriptions')
