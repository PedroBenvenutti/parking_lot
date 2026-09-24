"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-24 16:13:40.767996

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSequence(sa.Sequence("car_plate_seq")))
    op.create_table('task_types',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('icon', sa.String(length=16), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('is_manager', sa.Boolean(), nullable=False),
    sa.Column('is_valet', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('floors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id'),
    sa.UniqueConstraint('position')
    )
    op.create_table('valet_assignments',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('task_type_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['task_type_id'], ['task_types.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'task_type_id')
    )
    op.create_table('cars',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plate', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('task_type_id', sa.Integer(), nullable=False),
    sa.Column('effort', sa.Enum('moto', 'carro', 'caminhao', name='effort', native_enum=False, length=20), nullable=False),
    sa.Column('priority', sa.Enum('baixa', 'media', 'alta', 'urgente', name='priority', native_enum=False, length=20), nullable=False),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Enum('patio', 'estacionado', 'concluido', name='carstatus', native_enum=False, length=20), nullable=False),
    sa.Column('hazard_on', sa.Boolean(), nullable=False),
    sa.Column('floor_id', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ),
    sa.ForeignKeyConstraint(['task_type_id'], ['task_types.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('plate')
    )
    op.create_table('spots',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('floor_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('row', sa.Integer(), nullable=False),
    sa.Column('column', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('floor_id', 'position'),
    sa.UniqueConstraint('floor_id', 'row', 'column')
    )
    op.create_table('car_spots',
    sa.Column('car_id', sa.Integer(), nullable=False),
    sa.Column('spot_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['car_id'], ['cars.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['spot_id'], ['spots.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('car_id', 'spot_id'),
    sa.UniqueConstraint('spot_id')
    )
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('car_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('created', 'parked', 'moved_spot', 'updated', 'hazard_on', 'hazard_off', 'returned_to_patio', 'completed', name='eventtype', native_enum=False, length=20), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['car_id'], ['cars.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_car_id'), 'events', ['car_id'], unique=False)
    op.create_index(op.f('ix_events_timestamp'), 'events', ['timestamp'], unique=False)

    # Log de eventos imutável: bloqueia UPDATE e DELETE (TRUNCATE continua possível para reset/seed).
    op.execute(
        """
        CREATE FUNCTION events_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'events is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_no_update_delete
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION events_immutable();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS events_no_update_delete ON events")
    op.execute("DROP FUNCTION IF EXISTS events_immutable()")
    op.drop_index(op.f('ix_events_timestamp'), table_name='events')
    op.drop_index(op.f('ix_events_car_id'), table_name='events')
    op.drop_table('events')
    op.drop_table('car_spots')
    op.drop_table('spots')
    op.drop_table('cars')
    op.drop_table('valet_assignments')
    op.drop_table('floors')
    op.drop_table('users')
    op.drop_table('task_types')
    op.execute(sa.schema.DropSequence(sa.Sequence("car_plate_seq")))
