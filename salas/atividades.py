from core.atividades import data_hora, registra


# Descrições legíveis do histórico, ex.: "joao cancelou a reserva da Sala 101 de 22/11/2026 10:00"

def reserva(usuario, acao, obj):
    return registra(usuario, acao, obj,
                    f"{usuario.username} {acao} a reserva da {obj.sala.nome} de {data_hora(obj.data_inicio)}")


def sala(usuario, acao, obj):
    return registra(usuario, acao, obj, f"{usuario.username} {acao} a sala {obj.nome}")


def recurso(usuario, acao, obj):
    return registra(usuario, acao, obj,
                    f"{usuario.username} {acao} o recurso {obj.nome} na sala {obj.sala.nome}")
