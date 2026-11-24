import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import (
    Family,
    FamilySource,
    FilteredElementCollector,
    GroupTypeId,
    IFamilyLoadOptions,
    SpecTypeId,
    Transaction,
    TransactionStatus,
)


# 1. Classe de opções para autorizar o recarregamento da família sobrescrevendo a versão existente no projeto
class FamilyLoadOptions(IFamilyLoadOptions):

    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues.Value = True
        return True

    def OnSharedFamilyFound(
        self, sharedFamily, familyInUse, source, overwriteParameterValues
    ):
        source.Value = FamilySource.Family
        overwriteParameterValues.Value = True
        return True


def adicionar_parametros_a_familia(doc, nome_familia, lista_parametros):
    """Adiciona uma lista de parâmetros a uma família carregável (.rfa) no projeto.

    Requer que ``doc`` não tenha nenhuma transação ativa aberta (``doc.IsModifiable == False``),
    pois ``LoadFamily`` gerencia sua própria transação no documento de destino.

    :param doc: Documento ativo do Revit (.rvt)
    :param nome_familia: Nome exato da família no projeto (str)
    :param lista_parametros: Lista de dicionários contendo a definição dos parâmetros
    """
    if doc is None:
        print("Erro: Documento do Revit inválido (None).")
        return False

    if doc.IsModifiable:
        print(
            "Erro: O documento do projeto possui uma transação ativa. "
            "Feche a transação antes de chamar adicionar_parametros_a_familia."
        )
        return False

    # A. Localizar a família no banco de dados do projeto principal
    collector = FilteredElementCollector(doc).OfClass(Family)
    familia = next((f for f in collector if f.Name == nome_familia), None)

    if not familia:
        print(
            "Erro: A família '{}' não foi encontrada no projeto.".format(
                nome_familia
            )
        )
        return False

    if not familia.IsEditable:
        print(
            "Erro: A família '{}' é do sistema e não pode ser editada.".format(
                nome_familia
            )
        )
        return False

    # B. Abrir o documento da família (.rfa) em modo de edição na memória
    fam_doc = doc.EditFamily(familia)
    if not fam_doc:
        print(
            "Erro: Não foi possível abrir o documento da família '{}'.".format(
                nome_familia
            )
        )
        return False

    parametros_adicionados = 0
    t = Transaction(fam_doc, "Injeção de Parâmetros Automatizada")

    try:
        # C. Acessar o FamilyManager do arquivo da família
        fam_mgr = fam_doc.FamilyManager
        nomes_existentes = set(p.Definition.Name for p in fam_mgr.Parameters)

        # D. Iniciar uma Transação no documento da família
        t.Start()

        for p_def in lista_parametros:
            nome_param = p_def["nome"]
            grupo_param = p_def.get("grupo", GroupTypeId.Data)
            tipo_dado = p_def.get("tipo_dado", SpecTypeId.String.Text)
            is_instance = p_def.get("is_instance", True)

            # Verificar se o parâmetro já existe na família para evitar duplicatas
            if nome_param not in nomes_existentes:
                # Criar novo parâmetro de família (Revit API 2024+ com GroupTypeId)
                fam_mgr.AddParameter(
                    nome_param, grupo_param, tipo_dado, is_instance
                )
                nomes_existentes.add(nome_param)
                parametros_adicionados += 1
                print("-> Parâmetro '{}' adicionado.".format(nome_param))
            else:
                print("-> Parâmetro '{}' já existe. Ignorado.".format(nome_param))

        status = t.Commit()
        if status != TransactionStatus.Committed:
            print(
                "Erro: A transação na família '{}' não foi confirmada ({}).".format(
                    nome_familia, status
                )
            )
            return False

        # E. Recarregar a família atualizada apenas se houve alteração
        if parametros_adicionados > 0:
            load_options = FamilyLoadOptions()
            fam_doc.LoadFamily(doc, load_options)
    except Exception as exc:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        print(
            "Erro ao editar a família '{}': {}".format(nome_familia, exc)
        )
        return False
    finally:
        # F. Fechar o documento da família na memória sem salvar no disco
        fam_doc.Close(False)

    print(
        "\nConcluído! {} parâmetros injetados na família '{}'.".format(
            parametros_adicionados, nome_familia
        )
    )
    return True
