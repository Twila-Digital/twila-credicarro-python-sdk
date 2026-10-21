from typing import Optional

from twila_credicarro import (
    ActionOwner,
    ActiveStep,
    DocumentStatus,
    DocumentType,
    PendingActionKind,
    ProposalDetails,
    ProposalDocument,
    ProposalParticipant,
    ProposalParticipantState,
    ProposalStatus,
    ProposalStep,
    ProposalType,
    StepSituation,
    get_pending_actions,
)


def _state(
    step: ProposalStep,
    owner: ActionOwner = ActionOwner.INTEGRATOR,
    documents: Optional[list[ProposalDocument]] = None,
) -> ProposalParticipantState:
    return ProposalParticipantState(
        active_step=ActiveStep(step=step, situation=StepSituation.AWAITING_SUBMISSION, action_owner=owner),
        documents=documents or [],
    )


def _proposal(
    buyer: Optional[ProposalParticipantState] = None,
    seller: Optional[ProposalParticipantState] = None,
    store: Optional[ProposalParticipantState] = None,
) -> ProposalDetails:
    return ProposalDetails(
        id="p",
        number=1,
        simulation_id="s",
        status=ProposalStatus.APPROVED,
        type=ProposalType.FINANCING,
        buyer=buyer,
        seller=seller,
        store=store,
    )


def _document(document_type: DocumentType, status: DocumentStatus) -> ProposalDocument:
    return ProposalDocument(type=document_type, status=status)


def test_send_documents_lists_only_pending_documents() -> None:
    buyer = _state(
        ProposalStep.DOCUMENT_SUBMISSION,
        documents=[
            _document(DocumentType.PROOF_OF_ADDRESS, DocumentStatus.PENDING),
            _document(DocumentType.PROOF_OF_INCOME, DocumentStatus.VALID),
            _document(DocumentType.CNH, DocumentStatus.PENDING),
        ],
    )

    [action] = _proposal(buyer=buyer).get_pending_actions()

    assert action.participant is ProposalParticipant.BUYER
    assert action.step is ProposalStep.DOCUMENT_SUBMISSION
    assert action.kind is PendingActionKind.SEND_DOCUMENTS
    assert action.document_types == (DocumentType.PROOF_OF_ADDRESS, DocumentType.CNH)


def test_correct_documents_lists_only_invalid_documents() -> None:
    seller = _state(
        ProposalStep.DOCUMENT_CORRECTION,
        documents=[
            _document(DocumentType.RG, DocumentStatus.INVALID),
            _document(DocumentType.CPF, DocumentStatus.VALID),
        ],
    )

    [action] = _proposal(seller=seller).get_pending_actions()

    assert action.participant is ProposalParticipant.SELLER
    assert action.kind is PendingActionKind.CORRECT_DOCUMENTS
    assert action.document_types == (DocumentType.RG,)


def test_vehicle_details_and_deposit_account_have_no_document_types() -> None:
    actions = _proposal(
        buyer=_state(ProposalStep.DEPOSIT_ACCOUNT), store=_state(ProposalStep.VEHICLE_DETAILS)
    ).get_pending_actions()

    assert [(a.participant, a.kind, a.document_types) for a in actions] == [
        (ProposalParticipant.BUYER, PendingActionKind.SEND_DEPOSIT_ACCOUNT, ()),
        (ProposalParticipant.STORE, PendingActionKind.SEND_VEHICLE_DETAILS, ()),
    ]


def test_actions_owned_by_others_are_ignored() -> None:
    proposal = _proposal(
        buyer=_state(ProposalStep.DOCUMENT_SUBMISSION, owner=ActionOwner.CUSTOMER),
        seller=_state(ProposalStep.VEHICLE_DETAILS, owner=ActionOwner.CREDICARRO),
        store=_state(ProposalStep.DEPOSIT_ACCOUNT, owner=ActionOwner.NONE),
    )

    assert proposal.get_pending_actions() == []


def test_steps_without_integrator_action_are_ignored() -> None:
    proposal = _proposal(
        buyer=_state(ProposalStep.SIGNATURE), store=_state(ProposalStep.PAYMENT), seller=_state(ProposalStep.INSPECTION)
    )

    assert get_pending_actions(proposal) == []


def test_participants_without_active_step_are_ignored() -> None:
    assert _proposal(buyer=ProposalParticipantState(), seller=None, store=None).get_pending_actions() == []
