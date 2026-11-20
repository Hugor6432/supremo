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


def serie_criada(usuario, recorrencia, sala, reservas):
    return registra(usuario, 'criou', recorrencia,
                    f"{usuario.username} criou uma série de {len(reservas)} reservas da {sala.nome} "
                    f"({recorrencia.resumo}), de {data_hora(reservas[0].data_inicio)} "
                    f"a {data_hora(reservas[-1].data_inicio)}",
                    organizacao=sala.organizacao)


def serie_cancelada(usuario, recorrencia, sala, quantidade, a_partir):
    return registra(usuario, 'cancelou', recorrencia,
                    f"{usuario.username} cancelou {quantidade} reservas da série da {sala.nome} "
                    f"a partir de {data_hora(a_partir)}",
                    organizacao=sala.organizacao)
