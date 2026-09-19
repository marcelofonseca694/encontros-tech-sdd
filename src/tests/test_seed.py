import datetime
import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

import seed
from models.event import Event
from seed_data import REFERENCE_EVENTS


def test_seed_catalogo_vazio_cria_dez_eventos():
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = None

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        result = seed.main()

    assert result == 0
    mock_db.add_all.assert_called_once()
    created_events = mock_db.add_all.call_args[0][0]
    assert len(created_events) == 10
    assert all(isinstance(event, Event) for event in created_events)
    mock_db.commit.assert_called_once()


def test_seed_catalogo_com_conteudo_nao_altera_nada():
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = MagicMock(spec=Event)

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        result = seed.main()

    assert result == 0
    mock_db.add_all.assert_not_called()
    mock_db.commit.assert_not_called()


def test_seed_bloqueada_por_evento_cadastrado_por_pessoa():
    # A semeadura não distingue origem: um evento cadastrado manualmente pela
    # aplicação bloqueia exatamente como qualquer catálogo não vazio (P4, P6).
    mock_db = MagicMock()
    evento_humano = Event(
        title="Meetup criado manualmente",
        description=None,
        date=datetime.datetime.utcnow(),
        location="Local qualquer",
    )
    mock_db.query.return_value.first.return_value = evento_humano

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        result = seed.main()

    assert result == 0
    mock_db.add_all.assert_not_called()
    mock_db.commit.assert_not_called()


def test_seed_armazenamento_indisponivel_retorna_falha():
    mock_db = MagicMock()
    mock_db.query.side_effect = SQLAlchemyError("conexão recusada")

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        result = seed.main()

    assert result == 1
    mock_db.add_all.assert_not_called()
    mock_db.commit.assert_not_called()


def test_seed_falha_no_meio_da_execucao_sem_estado_parcial():
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = None
    mock_db.commit.side_effect = SQLAlchemyError("conexão perdida durante o commit")

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        result = seed.main()

    assert result == 1
    mock_db.rollback.assert_called_once()


def test_seed_repeticao_e_inofensiva():
    # Primeira execução: catálogo vazio, semeia. Segunda: o catálogo já contém
    # os eventos da primeira (simulado pelo mock retornando um evento existente)
    # e nada é alterado (P5).
    mock_db_primeira = MagicMock()
    mock_db_primeira.query.return_value.first.return_value = None

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_primeira
        primeiro_resultado = seed.main()

    mock_db_segunda = MagicMock()
    mock_db_segunda.query.return_value.first.return_value = MagicMock(spec=Event)

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db_segunda
        segundo_resultado = seed.main()

    assert primeiro_resultado == 0
    assert segundo_resultado == 0
    mock_db_primeira.add_all.assert_called_once()
    mock_db_segunda.add_all.assert_not_called()


def test_seed_nunca_chama_event_service():
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = None

    with patch("seed.get_db") as mock_get_db, patch(
        "services.event_service.create_event"
    ) as mock_create_event:
        mock_get_db.return_value.__enter__.return_value = mock_db
        seed.main()

    mock_create_event.assert_not_called()


def test_datas_semeadas_sao_futuras_e_preservam_espacamento():
    now = datetime.datetime(2026, 1, 1, 12, 0, 0)
    shifted = seed._shifted_dates(now)

    assert len(shifted) == 10
    assert all(date > now for date in shifted)
    assert shifted[0] == now + datetime.timedelta(days=seed.DAYS_UNTIL_FIRST_EVENT)

    intervalos_originais = [
        REFERENCE_EVENTS[i + 1]["reference_date"] - REFERENCE_EVENTS[i]["reference_date"]
        for i in range(len(REFERENCE_EVENTS) - 1)
    ]
    intervalos_deslocados = [
        shifted[i + 1] - shifted[i] for i in range(len(shifted) - 1)
    ]
    assert intervalos_originais == intervalos_deslocados


def test_conteudo_semeado_corresponde_ao_conjunto_de_referencia():
    mock_db = MagicMock()
    mock_db.query.return_value.first.return_value = None

    with patch("seed.get_db") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_db
        seed.main()

    created_events = mock_db.add_all.call_args[0][0]
    for created, reference in zip(created_events, REFERENCE_EVENTS):
        assert created.title == reference["title"]
        assert created.description == reference["description"]
        assert created.location == reference["location"]


def test_edit_token_e_unico_e_imprevisivel_entre_execucoes():
    # A semeadura não gera token próprio: depende do default da coluna
    # (models/event.py), disparado em qualquer INSERT (D2 de design.md).
    token_default = Event.__table__.columns["edit_token"].default.arg
    tokens = {token_default(None) for _ in range(20)}

    assert len(tokens) == 20
    for token in tokens:
        uuid.UUID(token)
